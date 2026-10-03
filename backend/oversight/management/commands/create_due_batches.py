"""Create superintendent batches for every completed review period. Safe to run daily."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.db_context import acting_as_system
from oversight.service import create_due_batches


class Command(BaseCommand):
    help = "Create oversight batches for review periods that have ended."

    def add_arguments(self, parser):
        parser.add_argument("--today", type=date.fromisoformat, default=None)

    def handle(self, *args, **options):
        today = options["today"] or timezone.localdate()
        if today > timezone.localdate():
            raise CommandError(
                "--today cannot be in the future: periods still running would be closed early "
                "and later approvals never reviewed."
            )
        with transaction.atomic(), acting_as_system("create_due_batches"):
            created = create_due_batches(today)
        self.stdout.write(f"Created {len(created)} batch(es)")
