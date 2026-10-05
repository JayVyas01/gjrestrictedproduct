"""The demo SMS inbox: an OTP sender that stores codes in a table the demo UI can show.

Chosen only by settings (`OTP_SENDER = "demo.sender.DemoInboxOtpSender"`), which the startup
guard requires in demo mode and forbids outside it. It refuses to run unless DEMO_MODE.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from core.db_context import acting_as_system
from demo.models import DemoInboxMessage
from identity.models import User
from identity.views import display_name
from positions.service import positions_held

ENROLMENT = "Enrolment"


def _recipient_name(user_id: str | None) -> str:
    if not user_id:
        return ENROLMENT
    # Cross-owner read of one display name (the licensee's holder name or the officer's
    # position titles) for the demo inbox only. Not audited: it is demo-only, read-only and
    # shows nothing beyond what the persona picker already names.
    with acting_as_system("demo_inbox"):
        user = User.objects.get(user_id=user_id)
        positions = sorted(positions_held(user), key=lambda position: position.id)
        return display_name(user, positions)


class DemoInboxOtpSender:
    def send(self, contact: str, code: str, user_id: str | None = None) -> None:
        if not settings.DEMO_MODE:
            raise ImproperlyConfigured("DemoInboxOtpSender must not be used outside demo mode")
        DemoInboxMessage.objects.create(
            user_id=user_id or "",
            display_name=_recipient_name(user_id),
            contact_last4=contact[-4:],
            code=code,
        )
