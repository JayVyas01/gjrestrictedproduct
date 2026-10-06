"""The demo CSV files (A6, A7): the demo's test sheet, rebuilt from the database.

`export_all(directory)` writes three files, each with a header row, in UTF-8:
- parties.csv: every licensed business (GSTIN), signed up or not, with its phone on file, email
  and current password, its licences (`; `-joined, one entry per licence in licence order),
  their permissions and validity, and its current stock;
- officials.csv: every account that is not a party, with its sign-in role, email, current
  password and whether it must still change it;
- transactions.csv: every transaction, newest first, with its status and whom it waits for.

Each file is written to a temporary file in the same folder and then renamed over the old one,
so a reader never sees half a file. Rows are built before anything is written.

Demo mode only. It reads as SYSTEM (across every business and account) and decrypts GSTINs,
phones, emails and the passwords in `DemoCredential`. That is acceptable only because the demo
data is synthetic, the folder is local and gitignored (`demo-data/`), and nothing calls this
outside demo mode: the receivers check DEMO_MODE and `export_demo_csv` refuses without it. The
SYSTEM reads are not audited: they change nothing and the files are the demo's own test sheet.

Kept in step by `schedule_export()` (connected in `demo/receivers.py`): after a commit that
changed an account, licence, stock, transaction, decision or demo password, one export runs per
database transaction. A failure is logged on the "demo.csv" logger and never reaches the
request; the next change writes the files again.
"""

import contextlib
import csv
import logging
import os
import tempfile
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from catalogue.service import class_unit
from core.db_context import acting_as_system
from demo.models import DemoCredential
from identity.login import login_identity
from identity.models import User
from identity.roles import Role
from identity.views import display_name
from licensing.models import Licence, LicenceStatus
from licensing.service import current_period, current_permissions
from positions.service import current_holder, positions_held
from stock.models import StockBalance
from transactions.checks import fmt_qty
from transactions.models import Transaction, TransactionStatus

logger = logging.getLogger("demo.csv")

SYSTEM_JOB = "demo_csv_export"
JOIN = "; "

PARTY_COLUMNS = (
    "business_name",
    "gstin",
    "phone_on_file",
    "email",
    "password",
    "signed_up",
    "licence_numbers",
    "licence_types",
    "scopes",
    "talukas",
    "may_buy",
    "may_sell",
    "stock_limits",
    "per_transaction_limits",
    "valid_until",
    "current_stock",
)
OFFICIAL_COLUMNS = ("name_or_position", "login_role", "email", "password", "must_change_password")
TRANSACTION_COLUMNS = (
    "reference",
    "created_at",
    "seller",
    "buyer",
    "substance",
    "quantity",
    "unit",
    "status",
    "approval_chain",
    "waiting_for",
)
# Officials in sign-in order, then by name; "" = cannot sign in (an officer with no position).
LOGIN_ROLE_ORDER = (
    "LICENSING_AUTHORITY",
    "HEAD_AUTHORITY",
    "SUPERINTENDENT",
    "AREA_OFFICER",
    "SOFTWARE_OWNER",
    "",
)
# A cell a spreadsheet would run as a formula. Only free text a tester typed (the business name
# given at sign-up) can start like that; it gets a leading apostrophe.
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _yes_no(value: bool | None) -> str:
    return "" if value is None else ("yes" if value else "no")


def _qty(quantity, unit: str | None) -> str:
    return f"{fmt_qty(quantity)} {unit}" if unit else fmt_qty(quantity)


def _typed_text(value: str) -> str:
    return "'" + value if value.startswith(FORMULA_START) else value


def _passwords() -> dict[str, DemoCredential]:
    return {credential.user_id: credential for credential in DemoCredential.objects.all()}


# --- parties.csv -------------------------------------------------------------------------------


def _licence_columns(licences: list[Licence], today) -> dict[str, str]:
    columns = defaultdict(list)
    for licence in licences:
        permissions = current_permissions(licence)
        period = current_period(licence, today)
        unit = licence.substance.unit if licence.substance else class_unit(licence.substance_class)
        columns["licence_numbers"].append(licence.number())
        columns["licence_types"].append(licence.licence_type.name)
        columns["scopes"].append(licence.scope_name())
        columns["talukas"].append(licence.area.name)
        columns["may_buy"].append(_yes_no(permissions and permissions.may_buy))
        columns["may_sell"].append(_yes_no(permissions and permissions.may_sell))
        columns["stock_limits"].append(_qty(permissions.max_stock_qty, unit) if permissions else "")
        columns["per_transaction_limits"].append(
            _qty(permissions.max_per_transaction_qty, unit) if permissions else ""
        )
        columns["valid_until"].append(period.ends_on.isoformat() if period else "")
    return {name: JOIN.join(values) for name, values in columns.items()}


def _stock(gstin_index: str) -> str:
    balances = (
        StockBalance.objects.filter(gstin_index=gstin_index, quantity__gt=0)
        .select_related("substance")
        .order_by("substance__name")
    )
    return JOIN.join(
        f"{balance.substance.name} {_qty(balance.quantity, balance.substance.unit)}"
        for balance in balances
    )


def _party_rows(passwords: dict[str, DemoCredential]) -> list[dict]:
    today = timezone.localdate()
    by_business: dict[str, list[Licence]] = defaultdict(list)
    licences = Licence.objects.select_related(
        "licence_type", "substance", "substance_class", "area"
    ).order_by("id")
    for licence in licences:
        by_business[licence.gstin_index].append(licence)
    accounts = {
        user.licensee_gstin_index: user
        for user in User.objects.filter(role=Role.LICENSEE).exclude(licensee_gstin_index="")
    }
    rows = []
    for gstin_index, held in by_business.items():
        account = accounts.get(gstin_index)
        credential = passwords.get(account.user_id) if account else None
        active = [licence for licence in held if licence.status == LicenceStatus.ACTIVE]
        on_file = (active or held)[0]
        rows.append(
            {
                "business_name": (
                    _typed_text(credential.business_name)
                    if credential and credential.business_name
                    else held[0].holder_name
                ),
                "gstin": held[0].gstin(),
                "phone_on_file": on_file.contact(),
                "email": account.get_email() if account else "",
                "password": credential.password() if credential else "",
                "signed_up": _yes_no(account is not None),
                **_licence_columns(held, today),
                "current_stock": _stock(gstin_index),
            }
        )
    return sorted(rows, key=lambda row: (row["business_name"].lower(), row["gstin"]))


# --- officials.csv -----------------------------------------------------------------------------


def _official_rows(passwords: dict[str, DemoCredential]) -> list[dict]:
    rows = []
    for user in User.objects.exclude(role=Role.LICENSEE).order_by("id"):
        login_role, _ = login_identity(user)
        credential = passwords.get(user.user_id)
        rows.append(
            {
                "name_or_position": display_name(user, positions_held(user)),
                "login_role": login_role,
                "email": user.get_email(),
                "password": credential.password() if credential else "",
                "must_change_password": _yes_no(user.must_change_password),
            }
        )
    order = {role: index for index, role in enumerate(LOGIN_ROLE_ORDER)}
    return sorted(rows, key=lambda row: (order[row["login_role"]], row["name_or_position"]))


# --- transactions.csv --------------------------------------------------------------------------


def _waiting_for(tx: Transaction, holders: dict) -> str:
    if tx.status == TransactionStatus.AWAITING_BUYER:
        return f"Buyer: {tx.buyer_licence.holder_name}"
    position = {
        TransactionStatus.AWAITING_OFFICER: tx.designated_position,
        TransactionStatus.AWAITING_SUPERINTENDENT: tx.superintendent_position,
    }.get(tx.status)
    if position is None:
        return ""
    if position.id not in holders:
        holders[position.id] = current_holder(position)
    holder = holders[position.id]
    return f"{position.title} ({holder.get_email() if holder else 'vacant'})"


def _transaction_rows() -> list[dict]:
    holders: dict = {}  # position id -> current holder, read once per export
    sales = Transaction.objects.select_related(
        "seller_licence",
        "buyer_licence",
        "substance",
        "designated_position",
        "superintendent_position",
    ).order_by("-created_at", "-id")
    return [
        {
            "reference": tx.reference,
            "created_at": timezone.localtime(tx.created_at).strftime("%Y-%m-%d %H:%M"),
            "seller": tx.seller_licence.holder_name,
            "buyer": tx.buyer_licence.holder_name,
            "substance": tx.substance.name,
            "quantity": fmt_qty(tx.quantity),
            "unit": tx.unit,
            "status": tx.get_status_display(),
            "approval_chain": tx.get_approval_chain_display(),
            "waiting_for": _waiting_for(tx, holders),
        }
        for tx in sales
    ]


# --- writing -----------------------------------------------------------------------------------


def _write(directory: Path, name: str, columns: tuple[str, ...], rows: list[dict]) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=directory, prefix=f".{name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        # Readable by the host user too (the container writes as another uid on Linux).
        os.chmod(temporary, 0o644)
        os.replace(temporary, directory / name)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def export_all(directory) -> None:
    """Write parties.csv, officials.csv and transactions.csv into `directory` (created if
    missing). Callers must be in demo mode."""
    directory = Path(directory)
    with acting_as_system(SYSTEM_JOB):
        passwords = _passwords()
        files = (
            ("parties.csv", PARTY_COLUMNS, _party_rows(passwords)),
            ("officials.csv", OFFICIAL_COLUMNS, _official_rows(passwords)),
            ("transactions.csv", TRANSACTION_COLUMNS, _transaction_rows()),
        )
    directory.mkdir(parents=True, exist_ok=True)
    for name, columns, rows in files:
        _write(directory, name, columns, rows)


# --- keeping the files in step -----------------------------------------------------------------


def export_quietly() -> None:
    """Export to settings.DEMO_DATA_DIR in demo mode; log any failure instead of raising."""
    if not settings.DEMO_MODE:
        return
    try:
        export_all(settings.DEMO_DATA_DIR)
    except Exception:
        logger.exception("Demo CSV export failed; it will be retried at the next change")


class ExportAfterCommit:
    """The on-commit callback. `done` tells a callback that already ran (still listed by a
    test's captured callbacks) from one still waiting for its commit."""

    def __init__(self):
        self.done = False

    def __call__(self) -> None:
        self.done = True
        export_quietly()


def schedule_export() -> None:
    """Export once after the current database transaction commits (at once in autocommit).

    One per transaction: a callback already waiting in this transaction covers every later
    change. A rollback drops the waiting callback with the changes, so the next change in a
    new transaction schedules a fresh one.
    """
    connection = transaction.get_connection()
    for _, callback, _ in connection.run_on_commit:
        if isinstance(callback, ExportAfterCommit) and not callback.done:
            return
    transaction.on_commit(ExportAfterCommit())
