"""Create the very first Software Owner account.

Run once, on the server, by the deployer. Every later account is created through the
application's own audited provisioning flows (Phase 2 and Phase 4).
"""

import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from audit.service import record
from identity.models import User
from identity.roles import Role


class Command(BaseCommand):
    help = "Create the first Software Owner account (refuses if one already exists)."

    def handle(self, *args, **options):
        if User.objects.filter(role=Role.SOFTWARE_OWNER).exists():
            raise CommandError("A Software Owner already exists; use in-app provisioning instead.")
        contact = input("Registered OTP contact (phone or email): ").strip()
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            raise CommandError("Passwords do not match")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc

        with transaction.atomic():
            user = User.objects.create_user(
                role=Role.SOFTWARE_OWNER, password=password, contact=contact
            )
            record(
                action="account.bootstrap_owner_created",
                actor="create_software_owner",
                subject_type="user",
                subject_id=user.user_id,
            )
        self.stdout.write(f"Created Software Owner with user ID {user.user_id}")
