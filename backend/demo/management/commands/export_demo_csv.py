"""`manage.py export_demo_csv [--dir PATH]`: write the demo CSV files now (demo mode only).

The files are also rebuilt after every relevant change and at the end of `seed_demo`; this is
for a folder that was emptied or for another folder. See `demo/csv_export.py`.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from demo.csv_export import export_all


class Command(BaseCommand):
    help = "Write parties.csv, officials.csv and transactions.csv (demo mode only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir", default=None, help="Target folder (default: settings.DEMO_DATA_DIR)."
        )

    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError("export_demo_csv runs only in demo mode (DEMO_MODE=1).")
        directory = options["dir"] or settings.DEMO_DATA_DIR
        export_all(directory)
        self.stdout.write(f"Wrote the demo CSV files to {directory}.")
