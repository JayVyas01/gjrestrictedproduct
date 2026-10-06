"""Keep DemoCredential in step with password changes (A7), in demo mode only.

Connected in `DemoConfig.ready`; identity sends the signal without knowing the demo app exists.
"""

from django.conf import settings
from django.dispatch import receiver

from demo.models import DemoCredential
from identity.signals import password_changed


@receiver(password_changed, dispatch_uid="demo_credential_on_password_change")
def record_changed_password(sender, user, password, **kwargs) -> None:
    if settings.DEMO_MODE:
        DemoCredential.store(user.user_id, password)
