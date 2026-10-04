"""How one-time codes reach the user. The production provider is plugged in via settings.

Codes are only ever sent to the contact stored on the account, never to an address
supplied in the request.
"""

from typing import ClassVar, Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


class OtpSender(Protocol):
    def send(self, contact: str, code: str) -> None: ...


class ConsoleOtpSender:
    """Development only: prints the code. Refuses to run when DEBUG is off."""

    def send(self, contact: str, code: str) -> None:
        if not settings.DEBUG:
            raise ImproperlyConfigured("ConsoleOtpSender must not be used outside development")
        print(f"[DEV OTP] code {code} for contact ending {contact[-4:]}")


class OutboxOtpSender:
    """Tests only: keeps sent codes in memory so tests can read them."""

    outbox: ClassVar[list[tuple[str, str]]] = []

    def send(self, contact: str, code: str) -> None:
        self.outbox.append((contact, code))


def get_sender() -> OtpSender:
    return import_string(settings.OTP_SENDER)()
