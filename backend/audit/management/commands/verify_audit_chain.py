"""Scheduled integrity check: exits non-zero if the audit trail was altered."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from audit.verify import verify_chain
from core.db_context import SYSTEM_ROLE, set_actor


class Command(BaseCommand):
    help = "Recompute the audit hash chain and fail loudly if anything was altered."

    def handle(self, *args, **options):
        with transaction.atomic():
            set_actor(user_id="verify_audit_chain", role=SYSTEM_ROLE)
            report = verify_chain()
        if not report.ok:
            raise CommandError(
                f"Audit chain BROKEN at event {report.first_bad_event_id}: {report.problem}"
            )
        self.stdout.write(f"Audit chain OK ({report.checked} events)")
