"""User accounts.

Users never choose their own ID: it is generated here. The OTP contact is stored
encrypted and can only be set by trusted server code, never by the user.
"""

import secrets
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

from core import crypto
from identity.roles import Role

# No 0/O or 1/I, so IDs can be read aloud or copied without mistakes.
USER_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_user_id() -> str:
    return "GJ" + "".join(secrets.choice(USER_ID_ALPHABET) for _ in range(10))


class UserManager(BaseUserManager):
    def create_user(self, *, role: str, password: str, contact: str) -> "User":
        user = self.model(role=role)
        user.set_contact(contact)
        user.set_password(password)
        user.save()
        return user


class User(AbstractBaseUser):
    user_id = models.CharField(max_length=12, unique=True, default=generate_user_id, editable=False)
    role = models.CharField(max_length=32, choices=Role.choices)
    contact_encrypted = models.TextField()
    is_active = models.BooleanField(default=True)
    failed_login_count = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "user_id"
    REQUIRED_FIELDS = ["role"]

    objects = UserManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=Role.values), name="user_role_valid"
            ),
        ]

    def set_contact(self, contact: str) -> None:
        self.contact_encrypted = crypto.encrypt(contact)

    def get_contact(self) -> str:
        return crypto.decrypt(self.contact_encrypted)

    def has_role(self, *roles: str) -> bool:
        return self.is_active and self.role in roles


class OtpPurpose(models.TextChoices):
    LOGIN = "LOGIN", "Login second factor"


class OtpChallenge(models.Model):
    """One issued code. Closed when verified, superseded, expired-and-tried, or out of attempts."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="otp_challenges")
    purpose = models.CharField(max_length=16, choices=OtpPurpose.choices)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    closed_at = models.DateTimeField(null=True, blank=True)
