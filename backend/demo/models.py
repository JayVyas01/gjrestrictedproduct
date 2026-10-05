"""Demo-only tables. Synthetic data only; `make demo-reset` recreates the whole database.

Production code never reads these tables, and their endpoints answer 404 unless DEMO_MODE.
"""

from django.db import models


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
