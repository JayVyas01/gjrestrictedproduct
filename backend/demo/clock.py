"""Back-dating for the demo seed: run real service code as if it happened at a past moment.

Every timestamp in the app comes from `django.utils.timezone.now` (called through the module,
including `auto_now_add`, `timezone.localdate()`, OTP expiry and the audit log's `occurred_at`;
no app module imports `now` directly), so patching that one attribute moves them all together.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from unittest import mock

from django.utils import timezone


def days_ago(days: int, at: str = "10:00") -> datetime:
    """`days` days before today, at the "HH:MM" time in India (an aware datetime)."""
    day = timezone.localdate() - timedelta(days=days)
    return timezone.make_aware(datetime.combine(day, time.fromisoformat(at)))


def hours_ago(hours: int) -> datetime:
    return timezone.now() - timedelta(hours=hours)


@contextmanager
def at(moment: datetime) -> Iterator[None]:
    """Inside the block, "now" is `moment`. Never in the future: the seed only writes history."""
    if timezone.is_naive(moment):
        raise ValueError("The demo clock needs an aware datetime")
    if moment > timezone.now():
        raise ValueError("The demo clock cannot move into the future")
    with mock.patch("django.utils.timezone.now", return_value=moment):
        yield
