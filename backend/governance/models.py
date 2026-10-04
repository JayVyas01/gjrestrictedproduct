"""Maker-checker rule changes: an authority drafts a change to the catalogue (a new licence
type, a rule version or an approval threshold) and a different Head Authority officer decides
it. Only an approved change reaches the catalogue.

Proposals are written by SYSTEM through governance.service. Once decided (no longer
SUBMITTED) a proposal can never change, and it can never be deleted.
"""

from django.db import models


class ProposalKind(models.TextChoices):
    NEW_LICENCE_TYPE = "NEW_LICENCE_TYPE", "New licence type"
    RULE_VERSION = "RULE_VERSION", "New rule version"
    APPROVAL_THRESHOLD = "APPROVAL_THRESHOLD", "New approval threshold"


class ProposalStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    WITHDRAWN = "WITHDRAWN", "Withdrawn"


class RuleChangeProposal(models.Model):
    kind = models.CharField(max_length=32, choices=ProposalKind.choices)
    payload = models.JSONField()
    justification = models.TextField()
    drafted_by = models.CharField(max_length=12)
    drafted_role = models.CharField(max_length=32)
    drafted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=16, choices=ProposalStatus.choices, default=ProposalStatus.SUBMITTED
    )
    decided_by = models.CharField(max_length=12, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    applied_ref = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=ProposalKind.values), name="proposal_kind_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ProposalStatus.values),
                name="proposal_status_valid",
            ),
        ]
