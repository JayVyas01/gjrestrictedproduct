"""Create the very first Software Owner account.

Run once, on the server, by the deployer. Every later account is created through the
application's own audited provisioning flows (Phase 2 and Phase 4).
"""

import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from audit.service import record
from identity.models import User, email_index, normalise_email
from identity.roles import Role


class Command(BaseCommand):
    help = "Create the first Software Owner account (refuses if one already exists)."

    def handle(self, *args, **options):
        if User.objects.filter(role=Role.SOFTWARE_OWNER).exists():
            raise CommandError("A Software Owner already exists; use in-app provisioning instead.")
        contact = input("Registered OTP contact (phone or email): ").strip()
        email = normalise_email(input("Sign-in email: "))
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError("Enter a valid sign-in email") from exc
        if User.objects.filter(email_index=email_index(email)).exists():
            raise CommandError("That email already belongs to an account")
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            raise CommandError("Passwords do not match")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc

        with transaction.atomic():
            # The operator has just chosen this password, so it is not an issued one and need
            # not be changed at the first sign-in (must_change_password stays False).
            user = User.objects.create_user(
                role=Role.SOFTWARE_OWNER, password=password, contact=contact, email=email
            )
            record(
                action="account.bootstrap_owner_created",
                actor="create_software_owner",
                subject_type="user",
                subject_id=user.user_id,
            )
        self.stdout.write(f"Created Software Owner with user ID {user.user_id}")
