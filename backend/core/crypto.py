"""Field-level encryption and blind indexes for sensitive identifiers.

- encrypt/decrypt: reversible, for values we must show or use again (e.g. an OTP contact).
- blind_index: one-way keyed hash, for exact-match lookup (e.g. licence number) without
  storing the plaintext. Partial or fuzzy search is deliberately impossible.
"""

import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class DecryptionError(Exception):
    pass


def _fernet() -> Fernet:
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("Value could not be decrypted") from exc


def blind_index(value: str) -> str:
    normalised = value.strip().upper()
    key = settings.BLIND_INDEX_KEY.encode()
    return hmac.new(key, normalised.encode(), hashlib.sha256).hexdigest()
