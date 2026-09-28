"""Storage for the audit trail. Rows are never updated or deleted (enforced in migration 0002)."""

from django.db import models


class AuditEvent(models.Model):
    occurred_at = models.DateTimeField()
    actor = models.CharField(max_length=64, blank=True)  # user_id, job name, or "" if anonymous
    action = models.CharField(max_length=64)  # e.g. "login.succeeded"
    subject_type = models.CharField(max_length=64, blank=True)
    subject_id = models.CharField(max_length=64, blank=True)
    reason = models.CharField(max_length=255, blank=True)  # why sensitive data was accessed
    payload = models.JSONField(default=dict)
    prev_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64, unique=True)

    class Meta:
        db_table = "audit_auditevent"


class AuditChainHead(models.Model):
    """Single row holding the newest hash. Locking it makes appends happen one at a time."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    last_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "audit_auditchainhead"
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="audit_head_single_row")
        ]
