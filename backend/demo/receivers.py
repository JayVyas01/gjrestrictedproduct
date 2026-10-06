"""Demo-mode receivers, connected in `DemoConfig.ready`. Production code sends its signals
without knowing the demo app exists, and every receiver here does nothing outside demo mode.

- A password change is stored in DemoCredential (A7).
- A change to anything the CSV files show (accounts, licences and their validity, positions
  held, stock, transactions, decisions, demo passwords) schedules one CSV export after the
  commit (`demo/csv_export.py`, A6).
"""

from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from demo.csv_export import schedule_export
from demo.models import DemoCredential
from identity.models import User
from identity.signals import password_changed
from licensing.models import Licence, LicenceValidityPeriod
from positions.models import PersonnelAssignment
from stock.models import StockBalance
from transactions.models import Transaction, TransactionDecision

# Models whose rows appear in (or change) the CSV files.
EXPORTED = (
    User,
    Licence,
    LicenceValidityPeriod,
    PersonnelAssignment,
    StockBalance,
    Transaction,
    TransactionDecision,
    DemoCredential,
)
# A sign-in attempt saves only these on the account; nothing the files show changes.
SIGN_IN_FIELDS = frozenset({"last_login", "failed_login_count", "locked_until"})


@receiver(password_changed, dispatch_uid="demo_credential_on_password_change")
def record_changed_password(sender, user, password, **kwargs) -> None:
    if settings.DEMO_MODE:
        DemoCredential.store(user.user_id, password)


def export_after_change(sender, instance, raw=False, update_fields=None, **kwargs) -> None:
    if not settings.DEMO_MODE or raw:
        return
    if sender is User and update_fields and set(update_fields) <= SIGN_IN_FIELDS:
        return
    schedule_export()


for model in EXPORTED:
    post_save.connect(
        export_after_change, sender=model, dispatch_uid=f"demo_csv_save_{model._meta.label}"
    )
    post_delete.connect(
        export_after_change, sender=model, dispatch_uid=f"demo_csv_delete_{model._meta.label}"
    )
