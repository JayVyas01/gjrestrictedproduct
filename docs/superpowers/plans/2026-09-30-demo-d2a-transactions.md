# Demo D2a — Transactions, Designated-Officer Approval and Stock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tested backend for the transaction journey:
1. The seller looks up the buyer by GSTIN.
2. The system picks both parties' licences and runs permission, limit and stock checks, each failure with a plain-language reason.
3. The buyer confirms or rejects with a one-time code.
4. The designated officer approves or rejects with a one-time code.
5. On approval, stock moves from seller to buyer.

**Architecture:** Three new Django apps, each with plain service functions:
- `reasons`: configurable reason codes.
- `stock`: balances plus an append-only movement log.
- `transactions`: transaction records, append-only decisions, licence selection, checks, services and the API.

All transaction and stock **writes** go through services running inside `acting_as_system(...)`, after an application-level check of who may act. Row-level security lets only SYSTEM write. Reads are row-level-security-scoped:
- **Parties:** a transaction is visible to its parties by GSTIN index.
- **Officers:** a transaction is visible through the position(s) they currently hold.
- **Oversight:** Head Authority and Software Owner can read every transaction.

**Tech Stack:** Django 5.2, DRF 3.17, PostgreSQL 16, pytest-django. This is the same stack as Phase 1 and D1.

**Spec:** [`2026-09-28-licence-types-and-demo-design.md`](../specs/2026-09-28-licence-types-and-demo-design.md), Revision 3 (decisions D10–D14 and section 5b). **Builds on:** Phase 1 and D1, both merged into `dev`. **Next:** D2b adds buyer-rejection alerts and superintendent batch sign-off, using the `superintendent_position` stored here. **Roadmap:** [`2026-09-26-roadmap.md`](2026-09-26-roadmap.md)

## Global Constraints

- All Phase 1 and D1 constraints still apply. They are summarised in `docs/CODEMAP.md` section 4, and the key rules are listed below.
  - **Raise to roll back, return to commit.**
  - **`record()` is the last lock taken**, and audit payloads hold IDs and blind indexes only, **never personal data or raw input**.
  - `blind_index(context, value)` always takes a context.
  - Tests use `app_db`, never `transactional_db`.
  - Append-only tables get `REVOKE UPDATE, DELETE, TRUNCATE` **plus** triggers using `reject_append_only_change()` (from core 0002).
  - Every new party-owned table gets row-level-security policies in the migration that creates it.
- **Every task updates `docs/CODEMAP.md` in the same commit.** That means the roles table, the responsibility map, the test catalogue, the conventions and the "Last updated" line.
- **Lock order** (to avoid deadlocks), always in this order: user row, then OTP challenge rows, then transaction row, then stock balance rows (sorted by GSTIN index), then audit.
- **Designated officer:** the position covering the **seller licence's area** at `AreaLevel.TALUKA`. **Superintendent:** the position covering it at `AreaLevel.DISTRICT`. Both are stored on the transaction when it is created. A later transfer changes who holds the position, not which position it is.
- **Buyer lookup is by GSTIN only.** The seller sees only the buyer's registered name. Licence numbers are never shown to the other party.
- **Licence selection:** for each party, pick an eligible licence. Eligible means it covers the substance, `trading_permitted` is true today, and it allows the needed action (`may_sell` or `may_buy`, from `current_permissions(licence, substance)`). Prefer a **substance-scoped** licence over a class-scoped one; if still tied, take the **earliest id**.
- **Decisions** (buyer confirm or reject, officer approve or reject) each need a fresh one-time code (purpose `DECISION`).
  - A reject needs a reason code of the right kind.
  - A reason with `requires_text` needs a comment.
  - The buyer's comment is shown only to authority viewers.
- **Stock:** one balance per business (GSTIN index) per substance, never negative. It changes only through services, and every change writes an append-only `StockMovement`.
- **Quantities** are `Decimal` with 3 places. User-facing messages format them without trailing zeros (`600`, not `600.000`), followed by the substance's unit (`L` or `KG`).
- **Plain-language messages:** every refusal says what is wrong, and where possible what to do. Use the exact wording given in the tasks; the tests pin it.
- **Out of scope for D2a**, because D2b adds them: authority alerts and superintendent batches, flags and sign-off.

## Review Focus

1. **A buyer holds both a class licence and a substance licence covering the chosen substance.** The substance-scoped licence must be used. Tested in Task 3 (`test_substance_scoped_licence_is_preferred`).
2. **The seller's stock drops between creation and approval**, so the transfer can no longer succeed. The approval must be refused with the stock reason, no stock may move, and the status stays `AWAITING_OFFICER`. Tested in Task 5 (`test_approval_rechecks_stock`).
3. **The designated position changes hands after the transaction was created.** The new holder can decide and the old holder can't. Tested in Task 5 (`test_transferred_officer_cannot_decide`).
4. **A wrong one-time code on a decision** must be counted as a failed attempt, record no decision and leave the status unchanged. Tested in Task 5 (`test_wrong_code_records_no_decision_but_counts_attempt`).
5. **The seller enters their own GSTIN as the buyer.** This must be refused with a plain reason. Tested in Task 4 (`test_cannot_sell_to_own_business`).

## File Structure

```
backend/
  reasons/models.py, service.py, views.py, urls.py
  reasons/migrations/0001_initial.py (generated), 0002_seed_defaults.py
  stock/models.py, service.py, views.py, urls.py
  stock/migrations/0001_initial.py (generated), 0002_rls_and_append_only.py
  transactions/models.py              # Transaction, TransactionDecision, statuses
  transactions/selection.py           # select_licence()
  transactions/checks.py              # transaction_problems(), eligibility_problems(), fmt_qty()
  transactions/service.py             # find_buyer, start_transaction, cancel, request_decision_code, decide
  transactions/presenters.py          # transaction_summary(), transaction_detail()
  transactions/serializers.py, views.py, urls.py
  transactions/migrations/0001_initial.py (generated), 0002_rls_and_append_only.py
  identity/migrations/0009_otp_purpose_decision.py (generated)
  tests/conftest.py                   # + make_licensee, trade fixtures; make_licence(area=...)
  tests/test_reasons.py, test_stock.py, test_transaction_rules.py,
  tests/test_transaction_service.py, test_transaction_decisions.py, test_transaction_api.py
```

---

### Task 1: Configurable reason codes

**Files:**
- Create: `backend/reasons/__init__.py`, `apps.py`, `models.py`, `service.py`, `views.py`, `urls.py`, `migrations/__init__.py`
- Create (generated): `backend/reasons/migrations/0001_initial.py`
- Create: `backend/reasons/migrations/0002_seed_defaults.py`
- Modify: `backend/config/settings.py` (`INSTALLED_APPS`), `backend/config/urls.py`, `docs/CODEMAP.md`
- Test: `backend/tests/test_reasons.py`

**Interfaces:**
- Produces:
  - `reasons.models.ReasonKind` (`OFFICER_REJECTION`, `BUYER_REJECTION`, `SUPERINTENDENT_FLAG`)
  - `reasons.models.ReasonCode(kind, code, label, requires_text, active, sort_order)`
  - `reasons.service.InvalidReason(Exception)`
  - `reasons.service.active_reasons(kind: str) -> QuerySet[ReasonCode]`
  - `reasons.service.resolve_reason(kind: str, code: str, text: str) -> ReasonCode`
  - `GET /api/reason-codes?kind=<KIND>` (any logged-in user) returns 200 `[{code, label, requires_text}]`, or 400 for an unknown kind.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_reasons.py`:
```python
import pytest

from reasons.models import ReasonCode, ReasonKind
from reasons.service import InvalidReason, active_reasons, resolve_reason
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db


def test_defaults_are_seeded_for_every_kind(app_db):
    for kind in ReasonKind.values:
        codes = list(active_reasons(kind).values_list("code", flat=True))
        assert "OTHER" in codes
        assert len(codes) >= 4


def test_buyer_defaults_match_the_spec(app_db):
    labels = set(active_reasons(ReasonKind.BUYER_REJECTION).values_list("label", flat=True))
    assert {"I did not place this order", "Quantity does not match", "Wrong substance", "Terms dispute"} <= labels


def test_other_requires_text(app_db):
    with pytest.raises(InvalidReason, match="describe the reason"):
        resolve_reason(ReasonKind.OFFICER_REJECTION, "OTHER", "   ")
    reason = resolve_reason(ReasonKind.OFFICER_REJECTION, "OTHER", "Seal was broken")
    assert reason.code == "OTHER"


def test_unknown_or_inactive_code_is_rejected(app_db):
    with pytest.raises(InvalidReason, match="Choose a reason"):
        resolve_reason(ReasonKind.BUYER_REJECTION, "NO_SUCH_CODE", "")
    ReasonCode.objects.filter(kind=ReasonKind.BUYER_REJECTION, code="TERMS_DISPUTE").update(active=False)
    with pytest.raises(InvalidReason):
        resolve_reason(ReasonKind.BUYER_REJECTION, "TERMS_DISPUTE", "")


def test_code_of_another_kind_is_rejected(app_db):
    with pytest.raises(InvalidReason):
        resolve_reason(ReasonKind.BUYER_REJECTION, "TRANSPORTER_INVALID", "")


def test_admin_can_add_a_new_reason_without_code_change(app_db):
    ReasonCode.objects.create(
        kind=ReasonKind.OFFICER_REJECTION, code="SEAL_BROKEN", label="Seal broken", sort_order=50
    )
    assert resolve_reason(ReasonKind.OFFICER_REJECTION, "SEAL_BROKEN", "").label == "Seal broken"


def test_reason_code_api_lists_active_codes(app_db, client, make_user, otp_outbox):
    user = make_user()
    first = client.post(
        "/api/auth/login", {"user_id": user.user_id, "password": TEST_PASSWORD}, content_type="application/json"
    )
    client.post(
        "/api/auth/login/verify",
        {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
        content_type="application/json",
    )
    body = client.get("/api/reason-codes?kind=BUYER_REJECTION").json()
    assert {"code": "NOT_ORDERED", "label": "I did not place this order", "requires_text": False} in body
    assert client.get("/api/reason-codes?kind=NOPE").status_code == 400


def test_reason_code_api_requires_login(app_db, client):
    assert client.get("/api/reason-codes?kind=BUYER_REJECTION").status_code == 403
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_reasons.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'reasons'`.

- [ ] **Step 3: Write the app**

`backend/reasons/__init__.py` and `backend/reasons/migrations/__init__.py` are empty.

`backend/reasons/apps.py`:
```python
from django.apps import AppConfig


class ReasonsConfig(AppConfig):
    name = "reasons"
```

`backend/reasons/models.py`:
```python
"""Reason codes for rejections and flags, kept in a table so admins can add new ones
without a code change. "OTHER" exists for every kind and needs a free-text comment."""

from django.db import models


class ReasonKind(models.TextChoices):
    OFFICER_REJECTION = "OFFICER_REJECTION", "Officer rejection"
    BUYER_REJECTION = "BUYER_REJECTION", "Buyer rejection"
    SUPERINTENDENT_FLAG = "SUPERINTENDENT_FLAG", "Superintendent flag"


class ReasonCode(models.Model):
    kind = models.CharField(max_length=24, choices=ReasonKind.choices)
    code = models.CharField(max_length=40)
    label = models.CharField(max_length=200)
    requires_text = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "code"], name="unique_reason_per_kind"),
            models.CheckConstraint(condition=models.Q(kind__in=ReasonKind.values), name="reason_kind_valid"),
        ]

    def __str__(self) -> str:
        return self.label
```

`backend/reasons/service.py`:
```python
"""Look up and validate reason codes chosen by users."""

from django.db.models import QuerySet

from reasons.models import ReasonCode


class InvalidReason(Exception):
    pass


def active_reasons(kind: str) -> QuerySet[ReasonCode]:
    return ReasonCode.objects.filter(kind=kind, active=True).order_by("sort_order", "code")


def resolve_reason(kind: str, code: str, text: str) -> ReasonCode:
    reason = active_reasons(kind).filter(code=code).first()
    if reason is None:
        raise InvalidReason("Choose a reason from the list.")
    if reason.requires_text and not text.strip():
        raise InvalidReason("Please describe the reason in a few words.")
    return reason
```

`backend/reasons/views.py`:
```python
"""Reason-code list for dropdowns."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from reasons.models import ReasonKind
from reasons.service import active_reasons


class ReasonCodeListView(APIView):
    def get(self, request):
        kind = request.query_params.get("kind", "")
        if kind not in ReasonKind.values:
            return Response({"detail": "Unknown reason kind."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            [
                {"code": r.code, "label": r.label, "requires_text": r.requires_text}
                for r in active_reasons(kind)
            ]
        )
```

`backend/reasons/urls.py`:
```python
from django.urls import path

from reasons import views

urlpatterns = [path("reason-codes", views.ReasonCodeListView.as_view())]
```

Add `"reasons",` to `INSTALLED_APPS` after `"licensing",`, and add `path("api/", include("reasons.urls")),` to `config/urls.py`. Then run:
```bash
uv run --env-file .env.test python manage.py makemigrations reasons
```

`backend/reasons/migrations/0002_seed_defaults.py`:
```python
"""Default reason codes (spec D14). Admins may add more rows later; codes are never renamed."""

from django.db import migrations

DEFAULTS = {
    "OFFICER_REJECTION": [
        ("QUANTITY_MISMATCH", "Quantity mismatch (expected vs found)"),
        ("WEIGHT_MISMATCH", "Material weight mismatch"),
        ("TRANSPORTER_INVALID", "Transporter details invalid"),
        ("LICENCE_NOT_VALID", "Licence expired or not valid"),
    ],
    "BUYER_REJECTION": [
        ("NOT_ORDERED", "I did not place this order"),
        ("QUANTITY_WRONG", "Quantity does not match"),
        ("WRONG_SUBSTANCE", "Wrong substance"),
        ("TERMS_DISPUTE", "Terms dispute"),
    ],
    "SUPERINTENDENT_FLAG": [
        ("QUANTITY_UNUSUAL", "Quantity unusually high"),
        ("PATTERN_CONCERN", "Repeated pattern needs review"),
        ("TRANSPORT_CONCERN", "Transport details need checking"),
    ],
}


def seed(apps, schema_editor):
    ReasonCode = apps.get_model("reasons", "ReasonCode")
    for kind, rows in DEFAULTS.items():
        for order, (code, label) in enumerate(rows, start=1):
            ReasonCode.objects.create(kind=kind, code=code, label=label, sort_order=order * 10)
        ReasonCode.objects.create(kind=kind, code="OTHER", label="Other", requires_text=True, sort_order=999)


def unseed(apps, schema_editor):
    apps.get_model("reasons", "ReasonCode").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("reasons", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: Update CODEMAP and commit**

In `docs/CODEMAP.md`:
- Add a `### reasons` section to the responsibility map: models, service, views and urls, and both migrations.
- Add every new test to the test catalogue.
- Add to the "Any logged-in user" role row: may list reason codes.
- Add a convention: "Reason codes are data. Add a row, never rename a code."
- Update the count.

```bash
uv run ruff format . && uv run ruff check . && uv run --env-file .env.test python manage.py makemigrations --check --dry-run
git add reasons/ config/ tests/test_reasons.py ../docs/CODEMAP.md
git commit -m "feat: configurable reason codes with seeded defaults"
```

---

### Task 2: Stock balances and movements

**Files:**
- Create: `backend/stock/__init__.py`, `apps.py`, `models.py`, `service.py`, `views.py`, `urls.py`, `migrations/__init__.py`
- Create (generated): `backend/stock/migrations/0001_initial.py`
- Create: `backend/stock/migrations/0002_rls_and_append_only.py`
- Modify: `backend/config/settings.py`, `backend/config/urls.py`, `backend/tests/conftest.py`, `docs/CODEMAP.md`
- Test: `backend/tests/test_stock.py`

**Interfaces:**
- Consumes:
  - `acting_as_system`
  - `audit.service.record`
  - `catalogue.models.Substance`
  - the `make_user`, `catalogue` and `make_licence` fixtures
- Produces:
  - Models:
    - `stock.models.StockBalance(gstin_index, substance, quantity, updated_at)`
    - `stock.models.MovementReason` (`OPENING`, `TRANSACTION`)
    - `stock.models.StockMovement(gstin_index, substance, delta, balance_after, reason, transaction_reference, created_at)`
  - Service:
    - `stock.service.InsufficientStock(Exception)`
    - `stock.service.balance_of(gstin_index: str, substance: Substance) -> Decimal` (0 when there is no row)
    - `stock.service.set_opening_balance(*, gstin_index: str, substance: Substance, quantity: Decimal, by: str) -> StockBalance` (SYSTEM context; once per business per substance)
    - `stock.service.transfer(*, from_gstin_index: str, to_gstin_index: str, substance: Substance, quantity: Decimal, transaction_reference: str) -> None` (SYSTEM context; locks rows in sorted GSTIN-index order)
  - API: `GET /api/stock/mine` (LICENSEE only) returns 200 `[{substance_code, substance, quantity, unit}]`
  - Conftest fixture: `make_licensee(licence, **kwargs) -> User` (a LICENSEE linked to the licence's GSTIN)

- [ ] **Step 1: Write the fixture and failing tests**

Add to `backend/tests/conftest.py`, with the imports at the top of the file:
```python
from identity.models import User  # already imported
from identity.roles import Role  # already imported


@pytest.fixture
def make_licensee(db):
    """A LICENSEE account linked to the licence's business (as enrolment would create it)."""

    def _make(licence, contact="+919800000900") -> User:
        return User.objects.create_user(
            role=Role.LICENSEE,
            password=TEST_PASSWORD,
            contact=contact,
            licensee_gstin_index=licence.gstin_index,
        )

    return _make
```

`backend/tests/test_stock.py`:
```python
from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, transaction

from core.db_context import SYSTEM_ROLE, acting_as_system, set_actor
from identity.roles import Role
from stock.models import StockBalance, StockMovement
from stock.service import InsufficientStock, balance_of, set_opening_balance, transfer
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db
SELLER = "a" * 64
BUYER = "b" * 64


def opening(catalogue, index, qty):
    with acting_as_system("test"):
        return set_opening_balance(gstin_index=index, substance=catalogue.whisky, quantity=Decimal(qty), by="test")


def test_balance_is_zero_without_a_row(app_db, catalogue):
    with acting_as_system("test"):
        assert balance_of(SELLER, catalogue.whisky) == Decimal("0")


def test_opening_balance_is_recorded_once_with_a_movement(app_db, catalogue, audit_actions):
    opening(catalogue, SELLER, "400")
    with acting_as_system("test"):
        assert balance_of(SELLER, catalogue.whisky) == Decimal("400")
        movement = StockMovement.objects.get(gstin_index=SELLER)
        assert (movement.delta, movement.balance_after, movement.reason) == (Decimal("400"), Decimal("400"), "OPENING")
    assert audit_actions() == ["stock.opening_recorded"]
    with pytest.raises(ValueError, match="already recorded"):
        opening(catalogue, SELLER, "10")


def test_transfer_moves_stock_and_logs_both_sides(app_db, catalogue):
    opening(catalogue, SELLER, "400")
    with acting_as_system("test"):
        transfer(
            from_gstin_index=SELLER, to_gstin_index=BUYER, substance=catalogue.whisky,
            quantity=Decimal("150"), transaction_reference="TXTEST00001",
        )
        assert balance_of(SELLER, catalogue.whisky) == Decimal("250")
        assert balance_of(BUYER, catalogue.whisky) == Decimal("150")
        deltas = sorted(StockMovement.objects.filter(reason="TRANSACTION").values_list("delta", flat=True))
        assert deltas == [Decimal("-150"), Decimal("150")]


def test_transfer_refuses_more_than_the_seller_holds(app_db, catalogue):
    opening(catalogue, SELLER, "100")
    with pytest.raises(InsufficientStock):
        with acting_as_system("test"):
            transfer(
                from_gstin_index=SELLER, to_gstin_index=BUYER, substance=catalogue.whisky,
                quantity=Decimal("101"), transaction_reference="TXTEST00002",
            )
    with acting_as_system("test"):
        assert balance_of(SELLER, catalogue.whisky) == Decimal("100")


def test_database_never_allows_negative_stock(app_db, catalogue):
    opening(catalogue, SELLER, "10")
    with pytest.raises(IntegrityError):
        with transaction.atomic(), acting_as_system("test"):
            StockBalance.objects.filter(gstin_index=SELLER).update(quantity=Decimal("-1"))


def test_holder_sees_only_own_stock(app_db, catalogue, make_licence, make_licensee):
    licence = make_licence()
    opening(catalogue, licence.gstin_index, "50")
    opening(catalogue, BUYER, "70")
    holder = make_licensee(licence)
    with transaction.atomic():
        set_actor(user_id=holder.user_id, role=Role.LICENSEE)
        assert list(StockBalance.objects.values_list("quantity", flat=True)) == [Decimal("50.000")]
        assert StockMovement.objects.count() == 1


def test_only_system_can_write_stock(app_db, catalogue):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            set_actor(user_id="GJLICENSEE01", role=Role.LICENSEE)
            StockBalance.objects.create(gstin_index=SELLER, substance=catalogue.whisky, quantity=Decimal("1"))


def test_movements_are_append_only_even_for_owner(db, catalogue):
    opening(catalogue, SELLER, "10")
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            StockMovement.objects.update(delta=Decimal("999"))


def test_my_stock_api(app_db, client, catalogue, make_licence, make_licensee, otp_outbox):
    licence = make_licence()
    opening(catalogue, licence.gstin_index, "320")
    user = make_licensee(licence)
    first = client.post(
        "/api/auth/login", {"user_id": user.user_id, "password": TEST_PASSWORD}, content_type="application/json"
    )
    client.post(
        "/api/auth/login/verify",
        {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
        content_type="application/json",
    )
    assert client.get("/api/stock/mine").json() == [
        {"substance_code": "WHISKY", "substance": "Whisky", "quantity": "320.000", "unit": "L"}
    ]
```
The unused `SYSTEM_ROLE` import is allowed if ruff doesn't flag it; if it does, remove it.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_stock.py -v`
Expected: collection error, `No module named 'stock'`.

- [ ] **Step 3: Write the app**

`backend/stock/__init__.py` and `backend/stock/migrations/__init__.py` are empty.

`backend/stock/apps.py`:
```python
from django.apps import AppConfig


class StockConfig(AppConfig):
    name = "stock"
```

`backend/stock/models.py`:
```python
"""How much of each substance a licensed business holds (demo: seeded, moved on approval).

Balances are per business (GSTIN blind index) per substance and never negative. Every change
writes an append-only StockMovement, so the balance history can always be reconstructed.
"""

from django.db import models

from catalogue.models import Substance


class StockBalance(models.Model):
    gstin_index = models.CharField(max_length=64)
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["gstin_index", "substance"], name="one_balance_per_business_and_substance"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="stock_never_negative"),
        ]


class MovementReason(models.TextChoices):
    OPENING = "OPENING", "Opening balance"
    TRANSACTION = "TRANSACTION", "Approved transaction"


class StockMovement(models.Model):
    gstin_index = models.CharField(max_length=64)
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT)
    delta = models.DecimalField(max_digits=14, decimal_places=3)
    balance_after = models.DecimalField(max_digits=14, decimal_places=3)
    reason = models.CharField(max_length=16, choices=MovementReason.choices)
    transaction_reference = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

`backend/stock/service.py`:
```python
"""Read and move stock. Writes need a SYSTEM context (row-level security enforces it).

Lock order: balance rows are locked in sorted GSTIN-index order so two transfers between the
same businesses can never deadlock. Callers audit the business action (e.g. the approval).
"""

from decimal import Decimal

from django.db import transaction

from audit.service import record
from catalogue.models import Substance
from stock.models import MovementReason, StockBalance, StockMovement


class InsufficientStock(Exception):
    pass


def balance_of(gstin_index: str, substance: Substance) -> Decimal:
    row = StockBalance.objects.filter(gstin_index=gstin_index, substance=substance).first()
    return row.quantity if row else Decimal("0")


def set_opening_balance(*, gstin_index: str, substance: Substance, quantity: Decimal, by: str) -> StockBalance:
    with transaction.atomic():
        if StockBalance.objects.filter(gstin_index=gstin_index, substance=substance).exists():
            raise ValueError("An opening balance is already recorded for this business and substance")
        balance = StockBalance.objects.create(gstin_index=gstin_index, substance=substance, quantity=quantity)
        StockMovement.objects.create(
            gstin_index=gstin_index, substance=substance, delta=quantity,
            balance_after=quantity, reason=MovementReason.OPENING,
        )
        record(
            action="stock.opening_recorded", actor=by, subject_type="substance", subject_id=substance.code,
            payload={"gstin_index": gstin_index, "quantity": str(quantity)},
        )
    return balance


def _locked(gstin_index: str, substance: Substance) -> StockBalance:
    StockBalance.objects.get_or_create(gstin_index=gstin_index, substance=substance, defaults={"quantity": Decimal("0")})
    return StockBalance.objects.select_for_update().get(gstin_index=gstin_index, substance=substance)


def transfer(
    *, from_gstin_index: str, to_gstin_index: str, substance: Substance, quantity: Decimal, transaction_reference: str
) -> None:
    with transaction.atomic():
        rows = {index: _locked(index, substance) for index in sorted({from_gstin_index, to_gstin_index})}
        source, target = rows[from_gstin_index], rows[to_gstin_index]
        if source.quantity < quantity:
            raise InsufficientStock("The seller no longer has enough stock for this transaction")
        for row, delta in ((source, -quantity), (target, quantity)):
            row.quantity += delta
            row.save(update_fields=["quantity", "updated_at"])
            StockMovement.objects.create(
                gstin_index=row.gstin_index, substance=substance, delta=delta, balance_after=row.quantity,
                reason=MovementReason.TRANSACTION, transaction_reference=transaction_reference,
            )
```

`backend/stock/views.py`:
```python
"""The licensee's own stock (the view filters by GSTIN; row-level security enforces it too)."""

from rest_framework.response import Response
from rest_framework.views import APIView

from identity.permissions import role_required
from identity.roles import Role
from stock.models import StockBalance


class MyStockView(APIView):
    permission_classes = [role_required(Role.LICENSEE)]

    def get(self, request):
        rows = StockBalance.objects.select_related("substance").filter(
            gstin_index=request.user.licensee_gstin_index
        ).order_by("substance__name")
        return Response(
            [
                {"substance_code": r.substance.code, "substance": r.substance.name,
                 "quantity": str(r.quantity), "unit": r.substance.unit}
                for r in rows
            ]
        )
```

`backend/stock/urls.py`:
```python
from django.urls import path

from stock import views

urlpatterns = [path("stock/mine", views.MyStockView.as_view())]
```

Add `"stock",` to `INSTALLED_APPS` after `"reasons",`, add `path("api/", include("stock.urls")),`, then run `makemigrations stock`.

`backend/stock/migrations/0002_rls_and_append_only.py`:
```python
"""Stock access: holders read their own business; authorities and SYSTEM read all; only
SYSTEM writes. Balances change only via quantity; movements are append-only."""

from django.db import migrations

ROLE = "current_setting('app.role', true)"
OWN_GSTIN = (
    "(SELECT licensee_gstin_index FROM identity_user "
    "WHERE user_id = current_setting('app.user_id', true) AND licensee_gstin_index <> '')"
)
READERS = "('HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'LICENSING_AUTHORITY', 'SYSTEM')"

FORWARD = f"""
ALTER TABLE stock_stockbalance ENABLE ROW LEVEL SECURITY;
CREATE POLICY balance_read ON stock_stockbalance FOR SELECT TO gj_app
    USING (gstin_index = {OWN_GSTIN} OR {ROLE} IN {READERS});
CREATE POLICY balance_insert ON stock_stockbalance FOR INSERT TO gj_app WITH CHECK ({ROLE} = 'SYSTEM');
CREATE POLICY balance_update ON stock_stockbalance FOR UPDATE TO gj_app
    USING ({ROLE} = 'SYSTEM') WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON stock_stockbalance FROM gj_app;
GRANT UPDATE (quantity, updated_at) ON stock_stockbalance TO gj_app;

ALTER TABLE stock_stockmovement ENABLE ROW LEVEL SECURITY;
CREATE POLICY movement_read ON stock_stockmovement FOR SELECT TO gj_app
    USING (gstin_index = {OWN_GSTIN} OR {ROLE} IN {READERS});
CREATE POLICY movement_insert ON stock_stockmovement FOR INSERT TO gj_app WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON stock_stockmovement FROM gj_app;
CREATE TRIGGER movement_no_update_delete BEFORE UPDATE OR DELETE ON stock_stockmovement
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER movement_no_truncate BEFORE TRUNCATE ON stock_stockmovement
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();
"""  # SQL built only from the constants above; no user input.

BACKWARD = """
DROP TRIGGER movement_no_truncate ON stock_stockmovement;
DROP TRIGGER movement_no_update_delete ON stock_stockmovement;
DROP POLICY movement_insert ON stock_stockmovement;
DROP POLICY movement_read ON stock_stockmovement;
ALTER TABLE stock_stockmovement DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON stock_stockmovement TO gj_app;
REVOKE UPDATE (quantity, updated_at) ON stock_stockbalance FROM gj_app;
DROP POLICY balance_update ON stock_stockbalance;
DROP POLICY balance_insert ON stock_stockbalance;
DROP POLICY balance_read ON stock_stockbalance;
ALTER TABLE stock_stockbalance DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON stock_stockbalance TO gj_app;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("stock", "0001_initial"),
        ("identity", "0008_one_account_per_licensee_gstin"),
        ("core", "0002_append_only_guard"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
```
If ruff flags `S608` on the f-string, put `# noqa: S608` on the closing `"""` line, the same way as in `licensing/migrations/0002`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: Update CODEMAP and commit**

In `docs/CODEMAP.md`:
- Add a `### stock` section.
- Licensee role row: "sees own stock (`/api/stock/mine`)".
- Software Owner, Head Authority and Licensing Authority rows: they read all stock.
- SYSTEM row: SYSTEM writes stock.
- Add the new tests and update the count.

```bash
uv run ruff format . && uv run ruff check . && uv run --env-file .env.test python manage.py makemigrations --check --dry-run
git add stock/ config/ tests/conftest.py tests/test_stock.py ../docs/CODEMAP.md
git commit -m "feat: per-business stock balances with append-only movements and RLS"
```

---

### Task 3: Transaction records, licence selection and checks

**Files:**
- Create: `backend/transactions/__init__.py`, `apps.py`, `models.py`, `selection.py`, `checks.py`, `migrations/__init__.py`
- Create (generated): `backend/transactions/migrations/0001_initial.py`
- Create: `backend/transactions/migrations/0002_rls_and_append_only.py`
- Modify: `backend/config/settings.py`, `backend/tests/conftest.py` (`make_licence(area=...)`, plus a `trade` fixture), `docs/CODEMAP.md`
- Test: `backend/tests/test_transaction_rules.py`

**Interfaces:**
- Consumes:
  - `licensing.models.Licence`, `LicenceStatus`
  - `licensing.service.covers`, `trading_permitted`, `current_permissions(licence, substance)`
  - `stock.service.balance_of`
  - `positions.models.Position`
  - `reasons.models.ReasonCode`
  - `core.crypto.encrypt/decrypt`
- Produces:
  - `transactions.models.TransactionStatus` (`AWAITING_BUYER`, `AWAITING_OFFICER`, `APPROVED`, `REJECTED_BY_BUYER`, `REJECTED_BY_OFFICER`, `CANCELLED`)
  - `DecisionStep` (`BUYER`, `OFFICER`, `SELLER`) and `DecisionOutcome` (`CONFIRM`, `APPROVE`, `REJECT`, `CANCEL`)
  - `Transaction`, with fields:
    - `reference`
    - `seller_licence`, `buyer_licence`, `seller_gstin_index`, `buyer_gstin_index`
    - `substance`, `quantity`, `unit`
    - `transporter_name_encrypted`, `transporter_id_encrypted`, `vehicle_number_encrypted`, `route`
    - `designated_position`, `superintendent_position`
    - `status`, `created_by`, `created_at`, `decided_at`

    and methods `transporter_name()`, `transporter_id()` and `vehicle_number()`
  - `TransactionDecision(transaction, step, outcome, actor_user_id, position, reason, comment, otp_verified_at, created_at)`
  - `transactions.models.generate_reference() -> str`
  - `transactions.selection.select_licence(gstin_index: str, substance: Substance, action: str, on: date) -> Licence | None`, where `action` is `"sell"` or `"buy"`
  - `transactions.checks.fmt_qty(q: Decimal) -> str`
  - `transactions.checks.eligibility_problems(seller_licence, buyer_licence, substance) -> list[str]`
  - `transactions.checks.transaction_problems(*, seller_licence, buyer_licence, substance, quantity) -> list[str]`
  - Conftest changes:
    - `make_licence(..., area=None)`, where the default area is `org.sanand`
    - fixture `trade` returning `SimpleNamespace(seller_licence, buyer_licence, seller, buyer, officer, superintendent)` with opening stock: seller 400 L of whisky, buyer 0 L

- [ ] **Step 1: Write the fixtures and failing tests**

In `backend/tests/conftest.py`, give `make_licence`'s inner `_make` an `area=None` keyword and pass `area=area or org.sanand` to `record_licence`. Then add the following, with the imports at the top of the file:
```python
from decimal import Decimal  # already imported

from positions.service import assign
from stock.service import set_opening_balance

BUYER_GSTIN = "99BBBBB1111B1Z5"


@pytest.fixture
def trade(catalogue, org, make_licence, make_licensee, make_user):
    """A seller and a buyer (Retail/Spirits licences in Sanand), the Area Officer for Sanand,
    the District superintendent, and 400 L of whisky in the seller's stock."""
    seller_licence = make_licence(holder_name="Sanand Spirits Pvt Ltd", contact="+919800000201")
    buyer_licence = make_licence(gstin=BUYER_GSTIN, holder_name="Bopal Bar & Kitchen", contact="+919800000202")
    officer = make_user(role=Role.PERSONNEL, contact="+919800000301")
    superintendent = make_user(role=Role.PERSONNEL, contact="+919800000302")
    assign(org.area_officer, officer, by="test")
    assign(org.district_officer, superintendent, by="test")
    with acting_as_system("test"):
        set_opening_balance(
            gstin_index=seller_licence.gstin_index, substance=catalogue.whisky, quantity=Decimal("400"), by="test"
        )
    return SimpleNamespace(
        seller_licence=seller_licence, buyer_licence=buyer_licence,
        seller=make_licensee(seller_licence, contact="+919800000201"),
        buyer=make_licensee(buyer_licence, contact="+919800000202"),
        officer=officer, superintendent=superintendent,
    )
```

`backend/tests/test_transaction_rules.py`:
```python
from datetime import date
from decimal import Decimal

import pytest
from django.db import DatabaseError, transaction

from catalogue.models import LicenceTypeRule
from catalogue.service import add_rule_version
from core.db_context import acting_as_system, set_actor
from identity.roles import Role
from licensing.models import LicenceStatus
from licensing.service import set_status
from tests.conftest import BUYER_GSTIN, _permissions
from transactions.checks import eligibility_problems, fmt_qty, transaction_problems
from transactions.models import Transaction, TransactionDecision, generate_reference
from transactions.selection import select_licence

pytestmark = pytest.mark.django_db
TODAY = date(2026, 6, 1)


def test_fmt_qty_drops_trailing_zeros():
    assert fmt_qty(Decimal("600.000")) == "600"
    assert fmt_qty(Decimal("12.500")) == "12.5"


def test_reference_format():
    ref = generate_reference()
    assert ref.startswith("TX") and len(ref) == 12


def test_selects_licence_that_allows_the_action(app_db, catalogue, trade):
    with acting_as_system("test"):
        assert select_licence(trade.seller_licence.gstin_index, catalogue.whisky, "sell", TODAY) == trade.seller_licence
        assert select_licence(trade.buyer_licence.gstin_index, catalogue.whisky, "buy", TODAY) == trade.buyer_licence


def test_substance_scoped_licence_is_preferred(app_db, catalogue, make_licence):
    class_licence = make_licence(gstin=BUYER_GSTIN)
    whisky_licence = make_licence(gstin=BUYER_GSTIN, substance=catalogue.whisky)
    assert class_licence.id < whisky_licence.id
    with acting_as_system("test"):
        assert select_licence(whisky_licence.gstin_index, catalogue.whisky, "buy", TODAY) == whisky_licence


def test_expired_or_suspended_licence_is_not_selected(app_db, catalogue, trade):
    with acting_as_system("test"):
        assert select_licence(trade.seller_licence.gstin_index, catalogue.whisky, "sell", date(2027, 1, 1)) is None
        set_status(trade.seller_licence, LicenceStatus.SUSPENDED, by="test", reason="inspection")
        assert select_licence(trade.seller_licence.gstin_index, catalogue.whisky, "sell", TODAY) is None


def test_substance_override_can_forbid_selling(app_db, catalogue, make_licence):
    rum_rule = LicenceTypeRule.objects.create(licence_type=catalogue.retail, substance=catalogue.rum)
    add_rule_version(rum_rule, created_by="test", **_permissions(may_sell=False))
    licence = make_licence()
    with acting_as_system("test"):
        assert select_licence(licence.gstin_index, catalogue.rum, "sell", TODAY) is None
        assert select_licence(licence.gstin_index, catalogue.whisky, "sell", TODAY) == licence


def test_eligibility_problems_are_plain(app_db, catalogue):
    assert eligibility_problems(None, None, catalogue.whisky) == [
        "You have no valid licence that allows selling Whisky.",
        "This buyer has no valid licence that allows buying Whisky.",
    ]


def test_per_transaction_limit_message(app_db, catalogue, trade):
    with acting_as_system("test"):
        problems = transaction_problems(
            seller_licence=trade.seller_licence, buyer_licence=trade.buyer_licence,
            substance=catalogue.whisky, quantity=Decimal("600"),
        )
    assert "Quantity 600 L exceeds your licence's per-transaction limit of 500 L." in problems
    assert "Quantity 600 L exceeds the buyer's licence's per-transaction limit of 500 L." in problems


def test_stock_and_buyer_capacity_messages(app_db, catalogue, trade):
    with acting_as_system("test"):
        problems = transaction_problems(
            seller_licence=trade.seller_licence, buyer_licence=trade.buyer_licence,
            substance=catalogue.whisky, quantity=Decimal("450"),
        )
    assert "You have 400 L of Whisky in stock, which is less than 450 L." in problems


def test_buyer_stock_limit_message(app_db, catalogue, trade):
    from stock.service import set_opening_balance

    with acting_as_system("test"):
        set_opening_balance(gstin_index=trade.buyer_licence.gstin_index, substance=catalogue.whisky,
                            quantity=Decimal("900"), by="test")
        problems = transaction_problems(
            seller_licence=trade.seller_licence, buyer_licence=trade.buyer_licence,
            substance=catalogue.whisky, quantity=Decimal("200"),
        )
    assert problems == [
        "This sale would take the buyer's stock of Whisky to 1100 L, above their licence limit of 1000 L."
    ]


def test_valid_transaction_has_no_problems(app_db, catalogue, trade):
    with acting_as_system("test"):
        assert transaction_problems(
            seller_licence=trade.seller_licence, buyer_licence=trade.buyer_licence,
            substance=catalogue.whisky, quantity=Decimal("150"),
        ) == []


def make_raw_transaction(trade, catalogue, org):
    with acting_as_system("test"):
        return Transaction.objects.create(
            reference=generate_reference(), seller_licence=trade.seller_licence, buyer_licence=trade.buyer_licence,
            seller_gstin_index=trade.seller_licence.gstin_index, buyer_gstin_index=trade.buyer_licence.gstin_index,
            substance=catalogue.whisky, quantity=Decimal("10"), unit="L",
            transporter_name_encrypted="x", transporter_id_encrypted="x", vehicle_number_encrypted="x",
            route="Sanand to Bopal", designated_position=org.area_officer,
            superintendent_position=org.district_officer, created_by=trade.seller.user_id,
        )


def visible_to(user, role):
    with transaction.atomic():
        set_actor(user_id=user.user_id, role=role)
        return Transaction.objects.count()


def test_transaction_visibility(app_db, catalogue, org, trade, make_licence, make_licensee, make_user):
    make_raw_transaction(trade, catalogue, org)
    outsider = make_licensee(make_licence(gstin="99CCCCC2222C1Z5"), contact="+919800000999")
    stranger_officer = make_user(role=Role.PERSONNEL)
    head = make_user(role=Role.HEAD_AUTHORITY)
    assert visible_to(trade.seller, Role.LICENSEE) == 1
    assert visible_to(trade.buyer, Role.LICENSEE) == 1
    assert visible_to(trade.officer, Role.PERSONNEL) == 1
    assert visible_to(trade.superintendent, Role.PERSONNEL) == 1
    assert visible_to(head, Role.HEAD_AUTHORITY) == 1
    assert visible_to(outsider, Role.LICENSEE) == 0
    assert visible_to(stranger_officer, Role.PERSONNEL) == 0


def test_only_system_writes_and_only_status_changes(app_db, catalogue, org, trade):
    tx = make_raw_transaction(trade, catalogue, org)
    with transaction.atomic():
        set_actor(user_id=trade.seller.user_id, role=Role.LICENSEE)
        assert Transaction.objects.filter(pk=tx.pk).update(status="APPROVED") == 0
    with acting_as_system("test"):
        assert Transaction.objects.get(pk=tx.pk).status == "AWAITING_BUYER"
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic(), acting_as_system("test"):
            Transaction.objects.filter(pk=tx.pk).update(quantity=Decimal("999"))


def test_decisions_are_append_only_even_for_owner(db, catalogue, org, trade):
    tx = make_raw_transaction(trade, catalogue, org)
    with acting_as_system("test"):
        TransactionDecision.objects.create(transaction=tx, step="SELLER", outcome="CANCEL", actor_user_id="x")
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            TransactionDecision.objects.update(outcome="APPROVE")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_transaction_rules.py -v`
Expected: collection error, `No module named 'transactions'`.

- [ ] **Step 3: Write the models**

`backend/transactions/__init__.py` and `backend/transactions/migrations/__init__.py` are empty.

`backend/transactions/apps.py`:
```python
from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    name = "transactions"
```

`backend/transactions/models.py`:
```python
"""A seller-initiated transaction and the append-only decisions taken on it.

Only SYSTEM writes (services, after checking who may act). Only status and decided_at ever
change on a transaction. Transporter identifiers are encrypted. The designated officer and
superintendent POSITIONS are fixed at creation; whoever holds them acts.
"""

import secrets

from django.db import models

from catalogue.models import Substance
from core import crypto
from identity.models import USER_ID_ALPHABET
from licensing.models import Licence
from positions.models import Position
from reasons.models import ReasonCode


def generate_reference() -> str:
    return "TX" + "".join(secrets.choice(USER_ID_ALPHABET) for _ in range(10))


class TransactionStatus(models.TextChoices):
    AWAITING_BUYER = "AWAITING_BUYER", "Waiting for the buyer"
    AWAITING_OFFICER = "AWAITING_OFFICER", "Waiting for the officer"
    APPROVED = "APPROVED", "Approved"
    REJECTED_BY_BUYER = "REJECTED_BY_BUYER", "Rejected by the buyer"
    REJECTED_BY_OFFICER = "REJECTED_BY_OFFICER", "Rejected by the officer"
    CANCELLED = "CANCELLED", "Cancelled by the seller"


class DecisionStep(models.TextChoices):
    BUYER = "BUYER", "Buyer"
    OFFICER = "OFFICER", "Officer"
    SELLER = "SELLER", "Seller"


class DecisionOutcome(models.TextChoices):
    CONFIRM = "CONFIRM", "Confirmed"
    APPROVE = "APPROVE", "Approved"
    REJECT = "REJECT", "Rejected"
    CANCEL = "CANCEL", "Cancelled"


class Transaction(models.Model):
    reference = models.CharField(max_length=12, unique=True, default=generate_reference, editable=False)
    seller_licence = models.ForeignKey(Licence, on_delete=models.PROTECT, related_name="sales")
    buyer_licence = models.ForeignKey(Licence, on_delete=models.PROTECT, related_name="purchases")
    seller_gstin_index = models.CharField(max_length=64)
    buyer_gstin_index = models.CharField(max_length=64)
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=4)
    transporter_name_encrypted = models.TextField()
    transporter_id_encrypted = models.TextField()
    vehicle_number_encrypted = models.TextField()
    route = models.CharField(max_length=300)
    designated_position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="+")
    superintendent_position = models.ForeignKey(Position, on_delete=models.PROTECT, null=True, related_name="+")
    status = models.CharField(max_length=24, choices=TransactionStatus.choices, default=TransactionStatus.AWAITING_BUYER)
    created_by = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="transaction_quantity_positive"),
            models.CheckConstraint(condition=models.Q(status__in=TransactionStatus.values), name="transaction_status_valid"),
            models.CheckConstraint(
                condition=~models.Q(seller_gstin_index=models.F("buyer_gstin_index")), name="transaction_not_self"
            ),
        ]

    def transporter_name(self) -> str:
        return crypto.decrypt(self.transporter_name_encrypted)

    def transporter_id(self) -> str:
        return crypto.decrypt(self.transporter_id_encrypted)

    def vehicle_number(self) -> str:
        return crypto.decrypt(self.vehicle_number_encrypted)


class TransactionDecision(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="decisions")
    step = models.CharField(max_length=8, choices=DecisionStep.choices)
    outcome = models.CharField(max_length=8, choices=DecisionOutcome.choices)
    actor_user_id = models.CharField(max_length=12)
    position = models.ForeignKey(Position, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    reason = models.ForeignKey(ReasonCode, on_delete=models.PROTECT, null=True, blank=True)
    comment = models.TextField(blank=True)
    otp_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

Add `"transactions",` to `INSTALLED_APPS` after `"stock",`, then run `makemigrations transactions`.

`backend/transactions/migrations/0002_rls_and_append_only.py`:
```python
"""Who may see and change transactions.

Read: the seller's and buyer's businesses (GSTIN index), whoever currently holds the designated
or superintendent position, and Head Authority / Software Owner / SYSTEM. Write: SYSTEM only
(services check who may act first). Only status and decided_at can change. Decisions follow
their transaction's visibility and are append-only.
"""

from django.db import migrations

ROLE = "current_setting('app.role', true)"
OWN_GSTIN = (
    "(SELECT licensee_gstin_index FROM identity_user "
    "WHERE user_id = current_setting('app.user_id', true) AND licensee_gstin_index <> '')"
)
HELD = (
    "(SELECT a.position_id FROM positions_personnelassignment a "
    "JOIN identity_user u ON u.id = a.user_id "
    "WHERE u.user_id = current_setting('app.user_id', true) AND a.ended_at IS NULL)"
)
READERS = "('HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'SYSTEM')"

FORWARD = f"""
ALTER TABLE transactions_transaction ENABLE ROW LEVEL SECURITY;
CREATE POLICY tx_party_read ON transactions_transaction FOR SELECT TO gj_app
    USING (seller_gstin_index = {OWN_GSTIN} OR buyer_gstin_index = {OWN_GSTIN});
CREATE POLICY tx_officer_read ON transactions_transaction FOR SELECT TO gj_app
    USING (designated_position_id IN {HELD} OR superintendent_position_id IN {HELD});
CREATE POLICY tx_authority_read ON transactions_transaction FOR SELECT TO gj_app
    USING ({ROLE} IN {READERS});
CREATE POLICY tx_insert ON transactions_transaction FOR INSERT TO gj_app WITH CHECK ({ROLE} = 'SYSTEM');
CREATE POLICY tx_update ON transactions_transaction FOR UPDATE TO gj_app
    USING ({ROLE} = 'SYSTEM') WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON transactions_transaction FROM gj_app;
GRANT UPDATE (status, decided_at) ON transactions_transaction TO gj_app;

ALTER TABLE transactions_transactiondecision ENABLE ROW LEVEL SECURITY;
CREATE POLICY decision_read ON transactions_transactiondecision FOR SELECT TO gj_app
    USING (transaction_id IN (SELECT id FROM transactions_transaction));
CREATE POLICY decision_insert ON transactions_transactiondecision FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON transactions_transactiondecision FROM gj_app;
CREATE TRIGGER decision_no_update_delete BEFORE UPDATE OR DELETE ON transactions_transactiondecision
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER decision_no_truncate BEFORE TRUNCATE ON transactions_transactiondecision
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();
"""  # SQL built only from the constants above; no user input.

BACKWARD = """
DROP TRIGGER decision_no_truncate ON transactions_transactiondecision;
DROP TRIGGER decision_no_update_delete ON transactions_transactiondecision;
DROP POLICY decision_insert ON transactions_transactiondecision;
DROP POLICY decision_read ON transactions_transactiondecision;
ALTER TABLE transactions_transactiondecision DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON transactions_transactiondecision TO gj_app;
REVOKE UPDATE (status, decided_at) ON transactions_transaction FROM gj_app;
DROP POLICY tx_update ON transactions_transaction;
DROP POLICY tx_insert ON transactions_transaction;
DROP POLICY tx_authority_read ON transactions_transaction;
DROP POLICY tx_officer_read ON transactions_transaction;
DROP POLICY tx_party_read ON transactions_transaction;
ALTER TABLE transactions_transaction DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON transactions_transaction TO gj_app;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0001_initial"),
        ("identity", "0008_one_account_per_licensee_gstin"),
        ("positions", "0002_one_position_per_area"),
        ("core", "0002_append_only_guard"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
```
Handle `S608` the same way as in Task 2.

- [ ] **Step 4: Write selection and checks**

`backend/transactions/selection.py`:
```python
"""Pick the licence a business uses for a given substance and action.

Eligible: covers the substance, trading is permitted on the day, and the frozen permissions for
that substance allow the action. Preference: a licence scoped to that exact substance, then the
earliest recorded. Call inside a context that can read the business's licences (SYSTEM).
"""

from datetime import date

from catalogue.models import Substance
from licensing.models import Licence, LicenceStatus
from licensing.service import covers, current_permissions, trading_permitted


def _allows(licence: Licence, substance: Substance, action: str) -> bool:
    permissions = current_permissions(licence, substance)
    if permissions is None:
        return False
    return permissions.may_sell if action == "sell" else permissions.may_buy


def select_licence(gstin_index: str, substance: Substance, action: str, on: date) -> Licence | None:
    candidates = Licence.objects.filter(gstin_index=gstin_index, status=LicenceStatus.ACTIVE).order_by("id")
    eligible = [
        licence
        for licence in candidates
        if covers(licence, substance) and trading_permitted(licence, on) and _allows(licence, substance, action)
    ]
    eligible.sort(key=lambda licence: (licence.substance_id is None, licence.id))
    return eligible[0] if eligible else None
```

`backend/transactions/checks.py`:
```python
"""Plain-language checks for a proposed transaction. Each problem is one sentence the user can
act on. Run at creation and again at approval (stock may have changed in between)."""

from decimal import Decimal

from catalogue.models import Substance
from licensing.models import Licence
from licensing.service import current_permissions
from stock.service import balance_of


def fmt_qty(quantity: Decimal) -> str:
    return format(quantity.normalize(), "f")


def eligibility_problems(seller_licence: Licence | None, buyer_licence: Licence | None, substance: Substance) -> list[str]:
    problems = []
    if seller_licence is None:
        problems.append(f"You have no valid licence that allows selling {substance.name}.")
    if buyer_licence is None:
        problems.append(f"This buyer has no valid licence that allows buying {substance.name}.")
    return problems


def transaction_problems(
    *, seller_licence: Licence, buyer_licence: Licence, substance: Substance, quantity: Decimal
) -> list[str]:
    unit = substance.unit
    q = fmt_qty(quantity)
    problems = []
    for licence, whose in ((seller_licence, "your"), (buyer_licence, "the buyer's")):
        limit = current_permissions(licence, substance).max_per_transaction_qty
        if quantity > limit:
            problems.append(f"Quantity {q} {unit} exceeds {whose} licence's per-transaction limit of {fmt_qty(limit)} {unit}.")
    held = balance_of(seller_licence.gstin_index, substance)
    if quantity > held:
        problems.append(f"You have {fmt_qty(held)} {unit} of {substance.name} in stock, which is less than {q} {unit}.")
    after = balance_of(buyer_licence.gstin_index, substance) + quantity
    buyer_max = current_permissions(buyer_licence, substance).max_stock_qty
    if after > buyer_max:
        problems.append(
            f"This sale would take the buyer's stock of {substance.name} to {fmt_qty(after)} {unit}, "
            f"above their licence limit of {fmt_qty(buyer_max)} {unit}."
        )
    return problems
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass. (An UPDATE whose rows are hidden by the policy's USING clause affects 0 rows rather than raising.)

- [ ] **Step 6: Update CODEMAP and commit**

In `docs/CODEMAP.md`:
- Add a `### transactions` section with models, selection, checks and the migrations.
- Roles table: who can see transactions and why, citing `transactions/migrations/0002`. Seller and buyer see them by GSTIN, officers through the positions they hold, and Head Authority, Software Owner and SYSTEM see all.
- Conventions: the D2a lock order, and "transaction writes happen only through services under SYSTEM".
- Add the new tests and update the count.

```bash
uv run ruff format . && uv run ruff check . && uv run --env-file .env.test python manage.py makemigrations --check --dry-run
git add transactions/ config/ tests/conftest.py tests/test_transaction_rules.py ../docs/CODEMAP.md
git commit -m "feat: transaction records with RLS, licence selection and plain-language checks"
```

---

### Task 4: Starting, looking up and cancelling transactions

**Files:**
- Create: `backend/transactions/service.py`
- Modify: `docs/CODEMAP.md`
- Test: `backend/tests/test_transaction_service.py`

**Interfaces:**
- Consumes:
  - Task 3 (`select_licence`, `eligibility_problems`, `transaction_problems`, the models)
  - `positions.service.covering_position`, `positions.models.AreaLevel`
  - `licensing.service.GSTIN_PATTERN`
  - `core.crypto`, `acting_as_system`, `audit.service.record`
- Produces:
  - `transactions.service.TransactionRefused(Exception)`, which has `.reasons: list[str]`
  - `transactions.service.NotAllowed(Exception)`
  - `transactions.service.Transport` (frozen dataclass: `name`, `id_number`, `vehicle_number`, `route`)
  - `transactions.service.find_buyer(*, gstin: str, by: User) -> str | None`, which returns the buyer's registered name
  - `transactions.service.start_transaction(*, seller: User, buyer_gstin: str, substance: Substance, quantity: Decimal, transport: Transport) -> Transaction`
  - `transactions.service.cancel_transaction(*, reference: str, seller: User) -> Transaction`
  - `transactions.service.load_visible(reference: str) -> Transaction | None`, which reads under the caller's own row-level-security context

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_transaction_service.py`:
```python
from decimal import Decimal

import pytest
from django.db import transaction as db_transaction

from core.db_context import acting_as_system, set_actor
from identity.roles import Role
from tests.conftest import BUYER_GSTIN, DEMO_GSTIN
from transactions.models import Transaction, TransactionStatus
from transactions.service import (
    NotAllowed,
    TransactionRefused,
    Transport,
    cancel_transaction,
    find_buyer,
    start_transaction,
)

pytestmark = pytest.mark.django_db
TRANSPORT = Transport(name="Ravi Transport Co", id_number="GJ-TR-4411", vehicle_number="GJ01AB1234", route="Sanand to Bopal via SG Highway")


def as_user(user, role):
    set_actor(user_id=user.user_id, role=role)


def start(trade, catalogue, qty="150", gstin=BUYER_GSTIN):
    as_user(trade.seller, Role.LICENSEE)
    return start_transaction(
        seller=trade.seller, buyer_gstin=gstin, substance=catalogue.whisky,
        quantity=Decimal(qty), transport=TRANSPORT,
    )


def test_find_buyer_returns_registered_name_only(app_db, trade, audit_actions):
    as_user(trade.seller, Role.LICENSEE)
    assert find_buyer(gstin=" 99bbbbb1111b1z5 ", by=trade.seller) == "Bopal Bar & Kitchen"
    assert find_buyer(gstin="99ZZZZZ9999Z1Z5", by=trade.seller) is None
    assert find_buyer(gstin="not-a-gstin", by=trade.seller) is None
    assert audit_actions()[-2:] == ["transaction.buyer_lookup", "transaction.buyer_lookup"]


def test_buyer_lookup_audit_holds_no_gstin(app_db, trade):
    from audit.models import AuditEvent
    from core.db_context import SYSTEM_ROLE

    as_user(trade.seller, Role.LICENSEE)
    find_buyer(gstin=BUYER_GSTIN, by=trade.seller)
    with db_transaction.atomic():
        set_actor(user_id="test", role=SYSTEM_ROLE)
        payloads = [str(p) for p in AuditEvent.objects.values_list("payload", flat=True)]
    assert not any(BUYER_GSTIN in p for p in payloads)


def test_start_creates_transaction_routed_to_seller_area_officer(app_db, catalogue, org, trade, audit_actions):
    tx = start(trade, catalogue)
    assert tx.status == TransactionStatus.AWAITING_BUYER
    assert tx.designated_position == org.area_officer
    assert tx.superintendent_position == org.district_officer
    assert tx.seller_licence == trade.seller_licence and tx.buyer_licence == trade.buyer_licence
    assert tx.unit == "L" and tx.vehicle_number() == "GJ01AB1234"
    assert audit_actions()[-1] == "transaction.started"


def test_transporter_identifiers_are_encrypted(app_db, catalogue, trade):
    tx = start(trade, catalogue)
    assert "GJ01AB1234" not in tx.vehicle_number_encrypted
    assert "GJ-TR-4411" not in tx.transporter_id_encrypted


def test_over_limit_is_refused_with_plain_reasons(app_db, catalogue, trade):
    with pytest.raises(TransactionRefused) as refused:
        start(trade, catalogue, qty="600")
    assert "Quantity 600 L exceeds your licence's per-transaction limit of 500 L." in refused.value.reasons
    with acting_as_system("test"):
        assert Transaction.objects.count() == 0


def test_unknown_buyer_is_refused(app_db, catalogue, trade):
    with pytest.raises(TransactionRefused) as refused:
        start(trade, catalogue, gstin="99ZZZZZ9999Z1Z5")
    assert refused.value.reasons == ["This buyer has no valid licence that allows buying Whisky."]


def test_cannot_sell_to_own_business(app_db, catalogue, trade):
    with pytest.raises(TransactionRefused) as refused:
        start(trade, catalogue, gstin=DEMO_GSTIN)
    assert refused.value.reasons == ["You cannot sell to your own business."]


def test_area_without_officer_position_is_refused(app_db, catalogue, org, trade):
    from positions.models import Position

    with acting_as_system("test"):
        Position.objects.filter(pk=org.area_officer.pk).update(area=org.state)  # detach Sanand's post
    with pytest.raises(TransactionRefused) as refused:
        start(trade, catalogue)
    assert refused.value.reasons == ["No officer is responsible for your area yet. Please contact the Licensing Authority."]


def test_seller_can_cancel_only_while_awaiting_buyer(app_db, catalogue, trade, audit_actions):
    tx = start(trade, catalogue)
    cancelled = cancel_transaction(reference=tx.reference, seller=trade.seller)
    assert cancelled.status == TransactionStatus.CANCELLED
    assert audit_actions()[-1] == "transaction.cancelled"
    with pytest.raises(NotAllowed):
        cancel_transaction(reference=tx.reference, seller=trade.seller)


def test_buyer_cannot_cancel(app_db, catalogue, trade):
    tx = start(trade, catalogue)
    as_user(trade.buyer, Role.LICENSEE)
    with pytest.raises(NotAllowed):
        cancel_transaction(reference=tx.reference, seller=trade.buyer)
```

**Note for `test_area_without_officer_position_is_refused`:** `positions` has no row-level security, so the update works under any actor. Moving the Sanand position onto the state area would break the one-to-one rule if the state already had a position, which it doesn't in the `org` fixture. If `OneToOneField` rejects the move anyway, create a fresh taluka `Area` with no position under Ahmedabad, record the seller's licence there with `make_licence(area=...)`, and assert the same reason.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_transaction_service.py -v`
Expected: collection error (`transactions.service` does not exist).

- [ ] **Step 3: Write the service (part 1)**

`backend/transactions/service.py`:
```python
"""The transaction journey. Every write runs inside acting_as_system(...) AFTER checking in
plain Python who may act; row-level security only lets SYSTEM write.

Lock order (never reverse it): user row -> OTP challenge rows -> transaction row ->
stock balance rows (sorted) -> audit (record() last).
"""

from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from audit.service import record
from catalogue.models import Substance
from core import crypto
from core.db_context import acting_as_system
from identity.models import User
from licensing.models import Licence, LicenceStatus
from licensing.service import GSTIN_PATTERN
from positions.models import AreaLevel
from positions.service import covering_position
from transactions.checks import eligibility_problems, transaction_problems
from transactions.models import DecisionOutcome, DecisionStep, Transaction, TransactionDecision, TransactionStatus
from transactions.selection import select_licence

NO_OFFICER = "No officer is responsible for your area yet. Please contact the Licensing Authority."


class TransactionRefused(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


class NotAllowed(Exception):
    pass


@dataclass(frozen=True)
class Transport:
    name: str
    id_number: str
    vehicle_number: str
    route: str


def find_buyer(*, gstin: str, by: User) -> str | None:
    """The buyer's registered name, or None. Audited by blind index only."""
    gstin = gstin.strip().upper()
    if not GSTIN_PATTERN.match(gstin):
        return None
    index = crypto.blind_index("gstin", gstin)
    with acting_as_system("buyer_lookup"):
        licence = Licence.objects.filter(gstin_index=index, status=LicenceStatus.ACTIVE).order_by("id").first()
        record(
            action="transaction.buyer_lookup", actor=by.user_id,
            payload={"gstin_index": index, "found": licence is not None},
        )
    return licence.holder_name if licence else None


def _refusals(seller_licence, buyer_licence, substance, quantity) -> list[str]:
    problems = eligibility_problems(seller_licence, buyer_licence, substance)
    if problems:
        return problems
    return transaction_problems(
        seller_licence=seller_licence, buyer_licence=buyer_licence, substance=substance, quantity=quantity
    )


def start_transaction(
    *, seller: User, buyer_gstin: str, substance: Substance, quantity: Decimal, transport: Transport
) -> Transaction:
    buyer_index = crypto.blind_index("gstin", buyer_gstin.strip().upper())
    if buyer_index == seller.licensee_gstin_index:
        raise TransactionRefused(["You cannot sell to your own business."])
    today = timezone.localdate()
    with acting_as_system("start_transaction"):
        seller_licence = select_licence(seller.licensee_gstin_index, substance, "sell", today)
        buyer_licence = select_licence(buyer_index, substance, "buy", today)
        problems = _refusals(seller_licence, buyer_licence, substance, quantity)
        if problems:
            raise TransactionRefused(problems)
        designated = covering_position(seller_licence.area, AreaLevel.TALUKA)
        if designated is None:
            raise TransactionRefused([NO_OFFICER])
        tx = Transaction.objects.create(
            seller_licence=seller_licence, buyer_licence=buyer_licence,
            seller_gstin_index=seller_licence.gstin_index, buyer_gstin_index=buyer_licence.gstin_index,
            substance=substance, quantity=quantity, unit=substance.unit,
            transporter_name_encrypted=crypto.encrypt(transport.name),
            transporter_id_encrypted=crypto.encrypt(transport.id_number),
            vehicle_number_encrypted=crypto.encrypt(transport.vehicle_number),
            route=transport.route, designated_position=designated,
            superintendent_position=covering_position(seller_licence.area, AreaLevel.DISTRICT),
            created_by=seller.user_id,
        )
        record(action="transaction.started", actor=seller.user_id, subject_type="transaction", subject_id=tx.reference)
    return tx


def load_visible(reference: str) -> Transaction | None:
    """Read under the caller's own RLS context: None means not found OR not theirs to see."""
    return Transaction.objects.select_related("substance", "designated_position").filter(reference=reference).first()


def cancel_transaction(*, reference: str, seller: User) -> Transaction:
    tx = load_visible(reference)
    if tx is None or tx.seller_gstin_index != seller.licensee_gstin_index:
        raise NotAllowed("Only the seller can cancel this transaction.")
    with acting_as_system("cancel_transaction"):
        locked = Transaction.objects.select_for_update().get(pk=tx.pk)
        if locked.status != TransactionStatus.AWAITING_BUYER:
            raise NotAllowed("This transaction can no longer be cancelled.")
        locked.status = TransactionStatus.CANCELLED
        locked.decided_at = timezone.now()
        locked.save(update_fields=["status", "decided_at"])
        TransactionDecision.objects.create(
            transaction=locked, step=DecisionStep.SELLER, outcome=DecisionOutcome.CANCEL, actor_user_id=seller.user_id
        )
        record(action="transaction.cancelled", actor=seller.user_id, subject_type="transaction", subject_id=locked.reference)
    return locked
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: Update CODEMAP and commit**

In `docs/CODEMAP.md`:
- `transactions/service.py` row: the functions it provides and the lock order.
- Licensee role row: may look up a buyer by GSTIN, start a transaction and cancel it while it waits for the buyer.
- Add the new tests and update the count.

```bash
uv run ruff format . && uv run ruff check .
git add transactions/service.py tests/test_transaction_service.py ../docs/CODEMAP.md
git commit -m "feat: start, look up and cancel transactions with plain-language refusals"
```

---

### Task 5: One-time-code-signed decisions and stock transfer on approval

**Files:**
- Modify: `backend/identity/models.py` (`OtpPurpose.DECISION`), `backend/transactions/service.py`, `docs/CODEMAP.md`
- Create (generated): `backend/identity/migrations/0009_otp_purpose_decision.py`
- Test: `backend/tests/test_transaction_decisions.py`

**Interfaces:**
- Consumes:
  - `identity.otp.issue` and `verify`
  - `positions.service.positions_held`
  - `reasons.service.resolve_reason` and `InvalidReason`
  - `reasons.models.ReasonKind`
  - `stock.service.transfer` and `InsufficientStock`
  - Task 4's service
- Produces:
  - `OtpPurpose.DECISION`
  - `transactions.service.decision_role(tx: Transaction, user: User) -> str | None`, returning `"buyer"`, `"officer"` or `None` for who may decide **now**
  - `transactions.service.request_decision_code(*, reference: str, user: User) -> OtpChallenge`, which raises `NotAllowed`
  - `transactions.service.decide(*, reference: str, user: User, challenge_id: str, code: str, outcome: str, reason_code: str = "", comment: str = "") -> Transaction | None`
    - Returns `None` for a wrong or expired code. It does not raise in that case, so the attempt is counted and committed.
    - Raises `NotAllowed` or `InvalidReason` **before** the code is used.
    - Raises `TransactionRefused` when the checks run again at approval and fail.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_transaction_decisions.py`:
```python
from decimal import Decimal

import pytest

from core.db_context import acting_as_system, set_actor
from identity import otp
from identity.models import OtpPurpose
from identity.roles import Role
from positions.service import assign
from reasons.service import InvalidReason
from stock.service import balance_of
from tests.conftest import BUYER_GSTIN
from transactions.models import TransactionDecision, TransactionStatus
from transactions.service import (
    NotAllowed,
    TransactionRefused,
    Transport,
    decide,
    request_decision_code,
    start_transaction,
)

pytestmark = pytest.mark.django_db
TRANSPORT = Transport(name="Ravi Transport Co", id_number="GJ-TR-4411", vehicle_number="GJ01AB1234", route="Sanand to Bopal")


def as_user(user, role):
    set_actor(user_id=user.user_id, role=role)


def new_tx(trade, catalogue, qty="150"):
    as_user(trade.seller, Role.LICENSEE)
    return start_transaction(seller=trade.seller, buyer_gstin=BUYER_GSTIN, substance=catalogue.whisky,
                             quantity=Decimal(qty), transport=TRANSPORT)


def act(user, role, tx, otp_outbox, outcome, reason_code="", comment="", code=None):
    as_user(user, role)
    challenge = request_decision_code(reference=tx.reference, user=user)
    return decide(reference=tx.reference, user=user, challenge_id=str(challenge.public_id),
                  code=code or otp_outbox[-1][1], outcome=outcome, reason_code=reason_code, comment=comment)


def test_happy_path_moves_stock_on_approval(app_db, catalogue, trade, otp_outbox, audit_actions):
    tx = new_tx(trade, catalogue)
    assert act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM").status == TransactionStatus.AWAITING_OFFICER
    approved = act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "APPROVE")
    assert approved.status == TransactionStatus.APPROVED and approved.decided_at is not None
    with acting_as_system("test"):
        assert balance_of(trade.seller_licence.gstin_index, catalogue.whisky) == Decimal("250")
        assert balance_of(trade.buyer_licence.gstin_index, catalogue.whisky) == Decimal("150")
        steps = list(TransactionDecision.objects.filter(transaction=tx).values_list("step", "outcome"))
    assert steps == [("BUYER", "CONFIRM"), ("OFFICER", "APPROVE")]
    assert audit_actions()[-2:] == ["transaction.buyer_confirmed", "transaction.approved"]


def test_decision_records_position_and_holder(app_db, catalogue, org, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "APPROVE")
    with acting_as_system("test"):
        officer_decision = TransactionDecision.objects.get(transaction=tx, step="OFFICER")
    assert officer_decision.position == org.area_officer
    assert officer_decision.actor_user_id == trade.officer.user_id
    assert officer_decision.otp_verified_at is not None


def test_buyer_reject_needs_a_buyer_reason(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    as_user(trade.buyer, Role.LICENSEE)
    with pytest.raises(InvalidReason):
        decide(reference=tx.reference, user=trade.buyer, challenge_id="00000000-0000-0000-0000-000000000000",
               code="123456", outcome="REJECT", reason_code="TRANSPORTER_INVALID")
    rejected = act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "REJECT", reason_code="NOT_ORDERED")
    assert rejected.status == TransactionStatus.REJECTED_BY_BUYER


def test_officer_reject_other_needs_text(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    with pytest.raises(InvalidReason, match="describe the reason"):
        act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "REJECT", reason_code="OTHER")
    rejected = act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "REJECT", reason_code="OTHER", comment="Seal broken")
    assert rejected.status == TransactionStatus.REJECTED_BY_OFFICER
    with acting_as_system("test"):
        assert balance_of(trade.seller_licence.gstin_index, catalogue.whisky) == Decimal("400")


def test_wrong_code_records_no_decision_but_counts_attempt(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    as_user(trade.buyer, Role.LICENSEE)
    challenge = request_decision_code(reference=tx.reference, user=trade.buyer)
    real = otp_outbox[-1][1]
    wrong = "000000" if real != "000000" else "111111"
    assert decide(reference=tx.reference, user=trade.buyer, challenge_id=str(challenge.public_id),
                  code=wrong, outcome="CONFIRM") is None
    challenge.refresh_from_db()
    assert challenge.attempts == 1
    with acting_as_system("test"):
        assert TransactionDecision.objects.filter(transaction=tx).count() == 0


def test_only_the_right_party_can_decide_at_each_step(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    as_user(trade.officer, Role.PERSONNEL)
    with pytest.raises(NotAllowed):
        request_decision_code(reference=tx.reference, user=trade.officer)  # buyer's turn
    as_user(trade.seller, Role.LICENSEE)
    with pytest.raises(NotAllowed):
        request_decision_code(reference=tx.reference, user=trade.seller)
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    as_user(trade.buyer, Role.LICENSEE)
    with pytest.raises(NotAllowed):
        request_decision_code(reference=tx.reference, user=trade.buyer)  # officer's turn


def test_buyer_cannot_approve_and_officer_cannot_confirm(app_db, catalogue, trade, otp_outbox):
    tx = new_tx(trade, catalogue)
    with pytest.raises(NotAllowed):
        act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "APPROVE")
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    with pytest.raises(NotAllowed):
        act(trade.officer, Role.PERSONNEL, tx, otp_outbox, "CONFIRM")


def test_transferred_officer_cannot_decide(app_db, catalogue, org, trade, otp_outbox, make_user):
    tx = new_tx(trade, catalogue)
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    replacement = make_user(role=Role.PERSONNEL, contact="+919800000303")
    assign(org.area_officer, replacement, by="test")
    as_user(trade.officer, Role.PERSONNEL)
    with pytest.raises(NotAllowed):
        request_decision_code(reference=tx.reference, user=trade.officer)
    assert act(replacement, Role.PERSONNEL, tx, otp_outbox, "APPROVE").status == TransactionStatus.APPROVED


def test_approval_rechecks_stock(app_db, catalogue, trade, otp_outbox, make_licence, make_licensee):
    first = new_tx(trade, catalogue, qty="300")
    second = new_tx(trade, catalogue, qty="300")
    for tx in (first, second):
        act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    act(trade.officer, Role.PERSONNEL, first, otp_outbox, "APPROVE")
    with pytest.raises(TransactionRefused) as refused:
        act(trade.officer, Role.PERSONNEL, second, otp_outbox, "APPROVE")
    assert "You have 100 L of Whisky in stock, which is less than 300 L." in refused.value.reasons
    with acting_as_system("test"):
        second.refresh_from_db()
        assert second.status == TransactionStatus.AWAITING_OFFICER
        assert balance_of(trade.seller_licence.gstin_index, catalogue.whisky) == Decimal("100")


def test_decision_code_is_bound_to_the_user(app_db, catalogue, trade, otp_outbox, make_user):
    tx = new_tx(trade, catalogue)
    act(trade.buyer, Role.LICENSEE, tx, otp_outbox, "CONFIRM")
    someone_else = make_user(role=Role.PERSONNEL, contact="+919800000304")
    foreign = otp.issue(someone_else, OtpPurpose.DECISION)  # a valid code, but not the officer's
    as_user(trade.officer, Role.PERSONNEL)
    with pytest.raises(NotAllowed, match="belongs to someone else"):
        decide(reference=tx.reference, user=trade.officer, challenge_id=str(foreign.public_id),
               code=otp_outbox[-1][1], outcome="APPROVE")
```

**Note for `test_approval_rechecks_stock`:** the refusal message says "You have …", because at approval the checks are worded from the seller's side. That's acceptable for the demo; the officer's screen shows the same sentence.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_transaction_decisions.py -v`
Expected: `ImportError` (`request_decision_code` and `decide` are not defined).

- [ ] **Step 3: Add the one-time-code purpose**

In `backend/identity/models.py`, add `DECISION = "DECISION", "Signing a decision"` to `OtpPurpose`, then run:
```bash
uv run --env-file .env.test python manage.py makemigrations identity --name otp_purpose_decision
```

- [ ] **Step 4: Write the service (part 2)**

Append to `backend/transactions/service.py`, adding these imports at the top:
```python
from identity import otp
from identity.models import OtpChallenge, OtpPurpose
from positions.service import positions_held
from reasons.models import ReasonKind
from reasons.service import resolve_reason
from stock.service import InsufficientStock, transfer
```

```python
WRONG_TURN = "This transaction is not waiting for your decision."
_ALLOWED = {"buyer": {DecisionOutcome.CONFIRM, DecisionOutcome.REJECT},
            "officer": {DecisionOutcome.APPROVE, DecisionOutcome.REJECT}}
_REASON_KIND = {"buyer": ReasonKind.BUYER_REJECTION, "officer": ReasonKind.OFFICER_REJECTION}


def decision_role(tx: Transaction, user: User) -> str | None:
    if tx.status == TransactionStatus.AWAITING_BUYER and user.licensee_gstin_index == tx.buyer_gstin_index:
        return "buyer"
    if tx.status == TransactionStatus.AWAITING_OFFICER and tx.designated_position in positions_held(user):
        return "officer"
    return None


def _for_decision(reference: str, user: User) -> tuple[Transaction, str]:
    tx = load_visible(reference)
    role = decision_role(tx, user) if tx else None
    if role is None:
        raise NotAllowed(WRONG_TURN)
    return tx, role


def request_decision_code(*, reference: str, user: User) -> OtpChallenge:
    _for_decision(reference, user)
    return otp.issue(user, OtpPurpose.DECISION)


def decide(
    *, reference: str, user: User, challenge_id: str, code: str, outcome: str, reason_code: str = "", comment: str = ""
) -> Transaction | None:
    tx, role = _for_decision(reference, user)
    if outcome not in _ALLOWED[role]:
        raise NotAllowed("That decision is not available at this step.")
    reason = resolve_reason(_REASON_KIND[role], reason_code, comment) if outcome == DecisionOutcome.REJECT else None
    signer = otp.verify(challenge_id=challenge_id, purpose=OtpPurpose.DECISION, code=code)
    if signer is None:
        return None  # wrong or expired code: the attempt counts, nothing else changes
    if signer.pk != user.pk:
        raise NotAllowed("This code belongs to someone else.")
    with acting_as_system("decide_transaction"):
        return _apply(tx, user, role, outcome, reason, comment)


def _apply(tx: Transaction, user: User, role: str, outcome: str, reason, comment: str) -> Transaction:
    locked = Transaction.objects.select_for_update().get(pk=tx.pk)
    if decision_role(locked, user) != role:
        raise NotAllowed(WRONG_TURN)
    now = timezone.now()
    if role == "officer" and outcome == DecisionOutcome.APPROVE:
        _approve(locked)
    locked.status = _NEXT[(role, outcome)]
    if locked.status != TransactionStatus.AWAITING_OFFICER:
        locked.decided_at = now
    locked.save(update_fields=["status", "decided_at"])
    TransactionDecision.objects.create(
        transaction=locked, step=DecisionStep.BUYER if role == "buyer" else DecisionStep.OFFICER,
        outcome=outcome, actor_user_id=user.user_id,
        position=locked.designated_position if role == "officer" else None,
        reason=reason, comment=comment.strip(), otp_verified_at=now,
    )
    record(action=_AUDIT[(role, outcome)], actor=user.user_id, subject_type="transaction", subject_id=locked.reference)
    return locked


def _approve(tx: Transaction) -> None:
    problems = _refusals(tx.seller_licence, tx.buyer_licence, tx.substance, tx.quantity)
    if problems:
        raise TransactionRefused(problems)
    try:
        transfer(from_gstin_index=tx.seller_gstin_index, to_gstin_index=tx.buyer_gstin_index,
                 substance=tx.substance, quantity=tx.quantity, transaction_reference=tx.reference)
    except InsufficientStock as exc:
        raise TransactionRefused([str(exc) + "."]) from exc


_NEXT = {
    ("buyer", DecisionOutcome.CONFIRM): TransactionStatus.AWAITING_OFFICER,
    ("buyer", DecisionOutcome.REJECT): TransactionStatus.REJECTED_BY_BUYER,
    ("officer", DecisionOutcome.APPROVE): TransactionStatus.APPROVED,
    ("officer", DecisionOutcome.REJECT): TransactionStatus.REJECTED_BY_OFFICER,
}
_AUDIT = {
    ("buyer", DecisionOutcome.CONFIRM): "transaction.buyer_confirmed",
    ("buyer", DecisionOutcome.REJECT): "transaction.buyer_rejected",
    ("officer", DecisionOutcome.APPROVE): "transaction.approved",
    ("officer", DecisionOutcome.REJECT): "transaction.officer_rejected",
}
```
`_approve` runs under SYSTEM, so `select_licence` isn't needed here. `_refusals` re-reads permissions and stock for the licences already fixed on the transaction.

The decision code is bound to its **user**, not to a single transaction. A user can only spend it on a transaction that is currently waiting for them. Say this in a comment on `request_decision_code`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass. The Phase 1 R10 lockout counts `LOGIN` codes only, so decision codes don't lock accounts.

- [ ] **Step 6: Update CODEMAP and commit**

In `docs/CODEMAP.md`:
- Roles table: the buyer confirms or rejects with a one-time code; the designated officer (the current holder of the seller area's Area Officer position) approves or rejects with a one-time code, and on approval stock moves.
- Identity row: the `DECISION` code purpose.
- Conventions: "Decisions verify the code BEFORE writing; a wrong code returns (commits the attempt); a refused approval raises (rolls back its writes)."
- Add the new tests and update the count.

```bash
uv run ruff format . && uv run ruff check . && uv run --env-file .env.test python manage.py makemigrations --check --dry-run
git add identity/ transactions/service.py tests/test_transaction_decisions.py ../docs/CODEMAP.md
git commit -m "feat: OTP-signed buyer and officer decisions; stock moves on approval"
```

---

### Task 6: Transaction API and timeline

**Files:**
- Create: `backend/transactions/presenters.py`, `serializers.py`, `views.py`, `urls.py`
- Modify: `backend/config/urls.py`, `backend/config/settings.py` (throttle `lookup`), `docs/CODEMAP.md`
- Test: `backend/tests/test_transaction_api.py`

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces:
  - `transactions.presenters.transaction_summary(tx: Transaction, viewer: User) -> dict` with keys `reference`, `status`, `status_label`, `substance`, `quantity`, `unit`, `seller_name`, `buyer_name`, `created_at` and `your_role`
  - `transactions.presenters.transaction_detail(tx: Transaction, viewer: User) -> dict`, which is the summary plus `transport`, `designated_officer`, `timeline` and `next_action`
  - HTTP API (every call needs a login):
    - `POST /api/transactions/buyer-lookup` with `{gstin}` returns 200 `{holder_name}` or 404 `{detail}`. Licensee only; `lookup` throttle, 30/min.
    - `POST /api/transactions` with `{buyer_gstin, substance_code, quantity, transporter_name, transporter_id_number, vehicle_number, route}` returns 201 with the detail, 422 `{detail, reasons}` or 400. Licensee only.
    - `GET /api/transactions` returns 200 `[summary]` for the transactions the caller can see, newest first, at most 50.
    - `GET /api/transactions/<ref>` returns 200 with the detail, or 404.
    - `POST /api/transactions/<ref>/decision-code` returns 200 `{challenge_id}` or 403 `{detail}`. `otp` throttle.
    - `POST /api/transactions/<ref>/decide` with `{challenge_id, code, outcome, reason_code?, comment?}` returns:
      - 200 with the detail
      - 401 `{detail: "The code is wrong or has expired. Request a new code."}`
      - 403, 400 `{detail}` or 422 `{detail, reasons}`
    - `POST /api/transactions/<ref>/cancel` returns 200 with the detail, or 403.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_transaction_api.py`:
```python
from decimal import Decimal

import pytest

from core.db_context import acting_as_system
from stock.service import balance_of
from tests.conftest import BUYER_GSTIN, TEST_PASSWORD

pytestmark = pytest.mark.django_db
NEW_TX = {
    "buyer_gstin": BUYER_GSTIN, "substance_code": "WHISKY", "quantity": "150",
    "transporter_name": "Ravi Transport Co", "transporter_id_number": "GJ-TR-4411",
    "vehicle_number": "GJ01AB1234", "route": "Sanand to Bopal via SG Highway",
}


def login(client, user, otp_outbox):
    client.logout()
    first = client.post("/api/auth/login", {"user_id": user.user_id, "password": TEST_PASSWORD},
                        content_type="application/json")
    client.post("/api/auth/login/verify", {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
                content_type="application/json")


def post(client, url, body=None):
    return client.post(url, body or {}, content_type="application/json")


def sign(client, ref, otp_outbox, outcome, **extra):
    challenge = post(client, f"/api/transactions/{ref}/decision-code").json()["challenge_id"]
    return post(client, f"/api/transactions/{ref}/decide",
                {"challenge_id": challenge, "code": otp_outbox[-1][1], "outcome": outcome, **extra})


def test_full_journey_over_http(app_db, client, catalogue, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    assert post(client, "/api/transactions/buyer-lookup", {"gstin": BUYER_GSTIN}).json() == {
        "holder_name": "Bopal Bar & Kitchen"
    }
    created = post(client, "/api/transactions", NEW_TX)
    assert created.status_code == 201
    ref = created.json()["reference"]
    assert created.json()["next_action"] == "Waiting for the buyer to confirm."

    login(client, trade.buyer, otp_outbox)
    assert sign(client, ref, otp_outbox, "CONFIRM").json()["status"] == "AWAITING_OFFICER"

    login(client, trade.officer, otp_outbox)
    detail = client.get(f"/api/transactions/{ref}").json()
    assert detail["your_role"] == "officer" and detail["next_action"] == "Your decision is needed."
    approved = sign(client, ref, otp_outbox, "APPROVE").json()
    assert approved["status"] == "APPROVED"
    assert [e["outcome"] for e in approved["timeline"]] == ["STARTED", "CONFIRM", "APPROVE"]
    with acting_as_system("test"):
        assert balance_of(trade.buyer_licence.gstin_index, catalogue.whisky) == Decimal("150")


def test_refused_transaction_returns_reasons(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    response = post(client, "/api/transactions", {**NEW_TX, "quantity": "600"})
    assert response.status_code == 422
    assert response.json()["detail"] == "This transaction can't go ahead."
    assert "Quantity 600 L exceeds your licence's per-transaction limit of 500 L." in response.json()["reasons"]


def test_invalid_input_is_400(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    assert post(client, "/api/transactions", {**NEW_TX, "vehicle_number": ""}).status_code == 400
    assert post(client, "/api/transactions", {**NEW_TX, "quantity": "-5"}).status_code == 400
    assert post(client, "/api/transactions", {**NEW_TX, "substance_code": "NOPE"}).status_code == 400


def test_unknown_buyer_lookup_is_404(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    response = post(client, "/api/transactions/buyer-lookup", {"gstin": "99ZZZZZ9999Z1Z5"})
    assert response.status_code == 404
    assert response.json()["detail"] == "No licensed business was found for this GSTIN. Check all 15 characters."


def test_wrong_code_is_401(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    ref = post(client, "/api/transactions", NEW_TX).json()["reference"]
    login(client, trade.buyer, otp_outbox)
    challenge = post(client, f"/api/transactions/{ref}/decision-code").json()["challenge_id"]
    real = otp_outbox[-1][1]
    wrong = "000000" if real != "000000" else "111111"
    response = post(client, f"/api/transactions/{ref}/decide", {"challenge_id": challenge, "code": wrong, "outcome": "CONFIRM"})
    assert response.status_code == 401


def test_outsider_cannot_see_transaction(app_db, client, trade, otp_outbox, make_licence, make_licensee):
    login(client, trade.seller, otp_outbox)
    ref = post(client, "/api/transactions", NEW_TX).json()["reference"]
    outsider = make_licensee(make_licence(gstin="99CCCCC2222C1Z5"), contact="+919800000999")
    login(client, outsider, otp_outbox)
    assert client.get(f"/api/transactions/{ref}").status_code == 404
    assert client.get("/api/transactions").json() == []


def test_buyer_comment_is_hidden_from_seller(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    ref = post(client, "/api/transactions", NEW_TX).json()["reference"]
    login(client, trade.buyer, otp_outbox)
    sign(client, ref, otp_outbox, "REJECT", reason_code="OTHER", comment="Never ordered from them")
    login(client, trade.seller, otp_outbox)
    seller_view = client.get(f"/api/transactions/{ref}").json()["timeline"][-1]
    assert seller_view["reason"] == "Other" and seller_view["comment"] is None
    login(client, trade.officer, otp_outbox)
    officer_view = client.get(f"/api/transactions/{ref}").json()["timeline"][-1]
    assert officer_view["comment"] == "Never ordered from them"


def test_seller_sees_buyer_name_but_not_licence_number(app_db, client, trade, otp_outbox):
    login(client, trade.seller, otp_outbox)
    detail = post(client, "/api/transactions", NEW_TX).json()
    assert detail["buyer_name"] == "Bopal Bar & Kitchen"
    assert "GJ/TEST" not in str(detail)  # licence numbers are never shown
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_transaction_api.py -v`
Expected: 404 on `/api/transactions/...`.

- [ ] **Step 3: Write the presenters**

`backend/transactions/presenters.py`:
```python
"""What each viewer sees of a transaction. Party names are read as SYSTEM (the other party's
licence is hidden from the viewer by RLS) and only the registered name is shown. The buyer's
and officer's free-text comments are shown to authority viewers only."""

from core.db_context import acting_as_system
from identity.models import User
from identity.roles import Role
from positions.service import positions_held
from transactions.checks import fmt_qty
from transactions.models import Transaction, TransactionStatus

_AUTHORITY_ROLES = {Role.HEAD_AUTHORITY, Role.SOFTWARE_OWNER}
_NEXT_ACTION = {
    TransactionStatus.AWAITING_BUYER: "Waiting for the buyer to confirm.",
    TransactionStatus.AWAITING_OFFICER: "Waiting for the officer's decision.",
}


def _role(tx: Transaction, viewer: User) -> str:
    if viewer.licensee_gstin_index == tx.seller_gstin_index:
        return "seller"
    if viewer.licensee_gstin_index == tx.buyer_gstin_index:
        return "buyer"
    held = positions_held(viewer)
    if tx.designated_position in held:
        return "officer"
    if tx.superintendent_position in held:
        return "superintendent"
    return "authority"


def _names(tx: Transaction) -> tuple[str, str]:
    with acting_as_system("transaction_view"):
        return tx.seller_licence.holder_name, tx.buyer_licence.holder_name


def transaction_summary(tx: Transaction, viewer: User) -> dict:
    seller_name, buyer_name = _names(tx)
    return {
        "reference": tx.reference, "status": tx.status, "status_label": tx.get_status_display(),
        "substance": tx.substance.name, "quantity": fmt_qty(tx.quantity), "unit": tx.unit,
        "seller_name": seller_name, "buyer_name": buyer_name,
        "created_at": tx.created_at.isoformat(), "your_role": _role(tx, viewer),
    }


def _next_action(tx: Transaction, role: str) -> str | None:
    if (tx.status, role) in {(TransactionStatus.AWAITING_BUYER, "buyer"), (TransactionStatus.AWAITING_OFFICER, "officer")}:
        return "Your decision is needed."
    return _NEXT_ACTION.get(tx.status)


def _timeline(tx: Transaction, show_comments: bool) -> list[dict]:
    events = [{"step": "SELLER", "outcome": "STARTED", "at": tx.created_at.isoformat(), "by": "Seller",
               "reason": None, "comment": None}]
    for d in tx.decisions.select_related("reason", "position").order_by("id"):
        events.append({
            "step": d.step, "outcome": d.outcome, "at": d.created_at.isoformat(),
            "by": d.position.title if d.position else d.get_step_display(),
            "reason": d.reason.label if d.reason else None,
            "comment": (d.comment or None) if show_comments else None,
        })
    return events


def transaction_detail(tx: Transaction, viewer: User) -> dict:
    summary = transaction_summary(tx, viewer)
    role = summary["your_role"]
    show_comments = role in {"officer", "superintendent", "authority"} or viewer.role in _AUTHORITY_ROLES
    return {
        **summary,
        "transport": {"name": tx.transporter_name(), "id_number": tx.transporter_id(),
                      "vehicle_number": tx.vehicle_number(), "route": tx.route},
        "designated_officer": tx.designated_position.title,
        "timeline": _timeline(tx, show_comments),
        "next_action": _next_action(tx, role),
    }
```

- [ ] **Step 4: Write the serializers, views and URLs**

`backend/transactions/serializers.py`:
```python
"""Input validation for the transaction API. Messages say what to fix."""

from rest_framework import serializers

from catalogue.models import Substance


class BuyerLookupSerializer(serializers.Serializer):
    gstin = serializers.CharField(max_length=20)


class NewTransactionSerializer(serializers.Serializer):
    buyer_gstin = serializers.CharField(max_length=20)
    substance_code = serializers.SlugRelatedField(slug_field="code", queryset=Substance.objects.all(),
                                                  source="substance")
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=0.001)
    transporter_name = serializers.CharField(max_length=120)
    transporter_id_number = serializers.CharField(max_length=40)
    vehicle_number = serializers.RegexField(r"^[A-Za-z]{2}\s?\d{1,2}\s?[A-Za-z]{0,3}\s?\d{4}$", max_length=16,
                                            error_messages={"invalid": "Enter the vehicle number like GJ01AB1234."})
    route = serializers.CharField(max_length=300)


class DecideSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")
    outcome = serializers.ChoiceField(choices=["CONFIRM", "APPROVE", "REJECT"])
    reason_code = serializers.CharField(max_length=40, required=False, default="")
    comment = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)
```
If DRF rejects `min_value=0.001` as a float, use `Decimal("0.001")` instead.

`backend/transactions/views.py`:
```python
"""HTTP endpoints for the transaction journey. Thin: validate, call a service, present.
Failures a user can fix are RETURNED (commit, e.g. a wrong code still counts); service
refusals raised inside a SYSTEM block have already rolled back their own writes."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from identity.permissions import role_required
from identity.roles import Role
from reasons.service import InvalidReason
from transactions.models import Transaction
from transactions.presenters import transaction_detail, transaction_summary
from transactions.serializers import BuyerLookupSerializer, DecideSerializer, NewTransactionSerializer
from transactions.service import (
    NotAllowed, TransactionRefused, Transport, cancel_transaction, decide, find_buyer,
    load_visible, request_decision_code, start_transaction,
)

NOT_FOUND = {"detail": "Transaction not found."}
WRONG_CODE = {"detail": "The code is wrong or has expired. Request a new code."}


def _refused(exc: TransactionRefused) -> Response:
    return Response({"detail": "This transaction can't go ahead.", "reasons": exc.reasons},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY)


def _forbidden(exc: Exception) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)


@method_decorator(csrf_protect, name="dispatch")
class BuyerLookupView(APIView):
    permission_classes = [role_required(Role.LICENSEE)]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "lookup"

    def post(self, request):
        data = BuyerLookupSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        name = find_buyer(gstin=data.validated_data["gstin"], by=request.user)
        if name is None:
            return Response({"detail": "No licensed business was found for this GSTIN. Check all 15 characters."},
                            status=status.HTTP_404_NOT_FOUND)
        return Response({"holder_name": name})


class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [role_required(Role.LICENSEE)()]
        return super().get_permissions()

    def get(self, request):
        rows = Transaction.objects.select_related("substance").order_by("-created_at")[:50]
        return Response([transaction_summary(tx, request.user) for tx in rows])

    def post(self, request):
        data = NewTransactionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        transport = Transport(name=v["transporter_name"], id_number=v["transporter_id_number"],
                              vehicle_number=v["vehicle_number"].upper().replace(" ", ""), route=v["route"])
        try:
            tx = start_transaction(seller=request.user, buyer_gstin=v["buyer_gstin"], substance=v["substance"],
                                   quantity=v["quantity"], transport=transport)
        except TransactionRefused as exc:
            return _refused(exc)
        return Response(transaction_detail(load_visible(tx.reference), request.user), status=status.HTTP_201_CREATED)


class TransactionDetailView(APIView):
    def get(self, request, reference):
        tx = load_visible(reference)
        if tx is None:
            return Response(NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        return Response(transaction_detail(tx, request.user))


class DecisionCodeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request, reference):
        try:
            challenge = request_decision_code(reference=reference, user=request.user)
        except NotAllowed as exc:
            return _forbidden(exc)
        return Response({"challenge_id": str(challenge.public_id)})


class DecideView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request, reference):
        data = DecideSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            tx = decide(reference=reference, user=request.user, challenge_id=str(v["challenge_id"]), code=v["code"],
                        outcome=v["outcome"], reason_code=v["reason_code"], comment=v["comment"])
        except NotAllowed as exc:
            return _forbidden(exc)
        except InvalidReason as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except TransactionRefused as exc:
            return _refused(exc)
        if tx is None:
            return Response(WRONG_CODE, status=status.HTTP_401_UNAUTHORIZED)
        return Response(transaction_detail(load_visible(reference), request.user))


class CancelView(APIView):
    permission_classes = [role_required(Role.LICENSEE)]

    def post(self, request, reference):
        try:
            cancel_transaction(reference=reference, seller=request.user)
        except NotAllowed as exc:
            return _forbidden(exc)
        return Response(transaction_detail(load_visible(reference), request.user))
```

`backend/transactions/urls.py`:
```python
from django.urls import path

from transactions import views

urlpatterns = [
    path("transactions", views.TransactionListView.as_view()),
    path("transactions/buyer-lookup", views.BuyerLookupView.as_view()),
    path("transactions/<str:reference>", views.TransactionDetailView.as_view()),
    path("transactions/<str:reference>/decision-code", views.DecisionCodeView.as_view()),
    path("transactions/<str:reference>/decide", views.DecideView.as_view()),
    path("transactions/<str:reference>/cancel", views.CancelView.as_view()),
]
```
The `buyer-lookup` route must come before `<str:reference>`, which it does.

Add `path("api/", include("transactions.urls")),` to `config/urls.py`, and add `"lookup": "30/min"` to `DEFAULT_THROTTLE_RATES`.

**Notes:**
- A `TransactionRefused` or `NotAllowed` raised inside `decide` is caught in the view **after** the `acting_as_system` savepoint has already rolled back its own writes. Returning a response then commits only what happened before the savepoint: the one-time code being used up, which is intended.
- `_approve` raising `TransactionRefused` also rolls back the stock `transfer`, because it sits inside the same savepoint.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 6: D2a acceptance, CODEMAP and commit**

In `docs/CODEMAP.md`:
- Add rows for the transactions presenters, serializers, views and urls.
- Add the API routes to the `config/urls.py` row, and the `lookup` rate limit to the `settings.py` row.
- Roles table:
  - The seller, buyer and officer each see their own view.
  - Comments are shown only to authority viewers.
  - The superintendent can **read** transactions in their district. Flagging and sign-off arrive in D2b.
- Add the new tests and update the count.

Run:
```bash
uv run ruff format --check . && uv run ruff check .
uv run --env-file .env.test python manage.py makemigrations --check --dry-run
uv run --env-file .env.test pytest -v
```
Expected: clean, `No changes detected`, all pass.

```bash
git add transactions/ config/ tests/test_transaction_api.py ../docs/CODEMAP.md
git commit -m "feat: transaction API with per-viewer detail and timeline"
```

---

## Spec coverage (D2a)

| Spec item (Revision 3) | Task |
|---|---|
| D12: buyer lookup by GSTIN; the system chooses licences, preferring substance-scoped ones | 3, 4, 6 |
| §5b checks with plain-language reasons, at creation and at approval | 3, 4, 5 |
| Mandatory transporter details, with identifiers encrypted | 3, 4, 6 |
| D10: one designated officer (seller's area, `TALUKA`), stored at creation, transfers respected | 3, 4, 5 |
| Buyer confirm/reject and officer approve/reject with a one-time code; reason required on reject; "Other" needs text | 5, 6 |
| D13: stock moves on approval, never negative, append-only movement log | 2, 5 |
| D14: configurable reason codes, three kinds, defaults seeded | 1 |
| Row-level-security visibility: parties, officer positions, superintendent position (read), authorities | 3, 6 |
| Buyer's comment visible to authorities only; seller sees the buyer's name, never licence numbers | 6 |
| Status timeline | 6 |
| Buyer-rejection alerts, superintendent batches, flags and sign-off | **Plan D2b** |
| Screens | **Plan D3** |
| Seed data (opening stock, personas, review periods) | **Plan D4** |
