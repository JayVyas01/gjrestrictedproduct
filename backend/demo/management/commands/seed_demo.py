"""Fill an empty demo database with the scripted, back-dated demo story (`demo/dataset.py`).

Demo mode only. Everything goes through the real services (see `demo/seed.py`) in one database
transaction, and the command fails, writing nothing, unless the audit chain verifies at the end.
"""

import time
from collections import Counter

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from alerts.models import AuthorityAlert
from audit.verify import verify_chain
from config.checks import DEMO_SENDER
from core.db_context import acting_as_system
from demo.seed import Seeder, SeedFailed
from governance.models import RuleChangeProposal
from identity.models import User
from licensing.models import Licence
from oversight.models import OversightBatch
from transactions.models import Transaction


class Command(BaseCommand):
    help = "Seed the demo database with a scripted history (demo mode, empty database only)."

    def handle(self, *args, **options):
        _refuse_unless_ready()
        started = time.monotonic()
        try:
            with transaction.atomic():
                Seeder().run()
                summary = _summary()
                with acting_as_system("verify_audit_chain"):
                    report = verify_chain()
                if not report.ok:
                    raise CommandError(
                        f"Audit chain BROKEN at event {report.first_bad_event_id}: "
                        f"{report.problem}. Nothing was seeded."
                    )
        except SeedFailed as exc:
            raise CommandError(f"{exc}. Nothing was seeded.") from exc
        self.stdout.write(summary)
        self.stdout.write(
            f"Audit chain OK ({report.checked} events). "
            f"Seeded in {time.monotonic() - started:.1f} s."
        )


def _refuse_unless_ready() -> None:
    if not settings.DEMO_MODE:
        raise CommandError("seed_demo runs only in demo mode (DEMO_MODE=1).")
    if settings.OTP_SENDER != DEMO_SENDER:
        raise CommandError(f"seed_demo needs the demo SMS inbox (OTP_SENDER={DEMO_SENDER}).")
    if not settings.DEMO_PASSWORD:
        raise CommandError("seed_demo needs DEMO_PASSWORD (see .env.demo).")
    try:
        validate_password(settings.DEMO_PASSWORD)
    except ValidationError as exc:
        raise CommandError("DEMO_PASSWORD is too weak: " + " ".join(exc.messages)) from exc
    with transaction.atomic(), acting_as_system("seed_demo"):
        if Licence.objects.exists():
            raise CommandError(
                "The database already has licences; seed_demo only fills an empty demo database "
                "(use make demo-reset)."
            )


def _summary() -> str:
    with acting_as_system("seed_demo_summary"):
        businesses = len(set(Licence.objects.values_list("gstin_index", flat=True)))
        statuses = Counter(Transaction.objects.values_list("status", flat=True))
        lines = [
            f"Seeded the demo: {businesses} businesses, {Licence.objects.count()} licences, "
            f"{User.objects.count()} accounts.",
            f"{sum(statuses.values())} transactions: "
            + ", ".join(f"{count} {status}" for status, count in sorted(statuses.items())),
            f"{OversightBatch.objects.count()} batches, "
            f"{AuthorityAlert.objects.count()} alerts, "
            f"{RuleChangeProposal.objects.count()} rule changes.",
        ]
    return "\n".join(lines)
