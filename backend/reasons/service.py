"""Look up and validate reason codes chosen by users."""

from django.db.models import QuerySet

from reasons.models import ReasonCode


class InvalidReason(Exception):
    pass


def active_reasons(kind: str) -> QuerySet[ReasonCode]:
    return ReasonCode.objects.filter(kind=kind, active=True).order_by("sort_order", "code")


def resolve_reason(kind: str, code: str, text: str) -> ReasonCode:
    reason = active_reasons(kind).filter(code=code).first()
    if reason is None:
        raise InvalidReason("Choose a reason from the list.")
    if reason.requires_text and not text.strip():
        raise InvalidReason("Please describe the reason in a few words.")
    return reason
