"""Demo-only tables. Synthetic data only; `make demo-reset` recreates the whole database.

Production code never reads these tables, and their endpoints answer 404 unless DEMO_MODE.
"""

from django.db import models

from core import crypto


class DemoInboxMessage(models.Model):
    """One code "sent" by the demo SMS inbox sender. Never holds the full contact."""

    user_id = models.CharField(max_length=12, blank=True)  # blank for subject codes (enrolment)
    display_name = models.CharField(max_length=200)
    contact_last4 = models.CharField(max_length=4)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["-created_at", "-id"], name="demo_inbox_newest")]


class DemoPersona(models.Model):
    """Which seeded account plays which persona in the demo script (filled by `seed_demo`)."""

    key = models.CharField(max_length=40, unique=True)
    user_id = models.CharField(max_length=12)


class DemoPendingSignup(models.Model):
    """A party sign-up waiting for its code (`demo/signup.py`), keyed by the code's challenge.

    Holds what the form gave until the code is entered, so the password never travels in a URL
    or the session: email, address and the password are encrypted, plus the password's hash.
    Deleted on completion; a row older than the code's lifetime is ignored.
    """

    challenge_public_id = models.UUIDField(unique=True)
    gstin_index = models.CharField(max_length=64, db_index=True)
    licence_id = models.BigIntegerField()  # the ACTIVE licence whose phone matched
    email_encrypted = models.TextField()
    business_name = models.CharField(max_length=200)
    address_encrypted = models.TextField()
    password_hash = models.CharField(max_length=128)
    password_encrypted = models.TextField()  # for DemoCredential only
    created_at = models.DateTimeField(auto_now_add=True)


class DemoCredential(models.Model):
    """The current password of a demo account (A7), for the persona picker and the CSV files.

    Demo only: written at seed, sign-up and password change. Encrypted at rest; only the demo
    endpoints and exports decrypt it. `business_name` is the name a party gave at sign-up (blank
    for seeded accounts), shown in parties.csv instead of the licence holder name.
    """

    user_id = models.CharField(max_length=12, unique=True)
    password_encrypted = models.TextField()
    business_name = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def store(cls, user_id: str, password: str) -> "DemoCredential":
        credential, _ = cls.objects.update_or_create(
            user_id=user_id, defaults={"password_encrypted": crypto.encrypt(password)}
        )
        return credential

    def password(self) -> str:
        return crypto.decrypt(self.password_encrypted)
