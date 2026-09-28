import pytest
from cryptography.fernet import Fernet

from core.crypto import DecryptionError, blind_index, decrypt, encrypt

CONTACT = "+91 98765 43210"


def test_encrypt_round_trip():
    assert decrypt(encrypt(CONTACT)) == CONTACT


def test_ciphertext_does_not_reveal_plaintext():
    assert "98765" not in encrypt(CONTACT)


def test_encryption_is_randomised():
    assert encrypt(CONTACT) != encrypt(CONTACT)


def test_decrypt_rejects_garbage():
    with pytest.raises(DecryptionError):
        decrypt("not-a-token")


def test_decrypt_rejects_value_encrypted_with_another_key(settings):
    token = encrypt(CONTACT)
    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    with pytest.raises(DecryptionError):
        decrypt(token)


def test_blind_index_is_deterministic_and_normalised():
    assert blind_index(" gj/lic/001 ") == blind_index("GJ/LIC/001")
    assert len(blind_index("GJ/LIC/001")) == 64


def test_blind_index_differs_between_values():
    assert blind_index("GJ/LIC/001") != blind_index("GJ/LIC/002")


def test_blind_index_depends_on_secret_key(settings):
    before = blind_index("GJ/LIC/001")
    settings.BLIND_INDEX_KEY = "another-test-key"
    assert blind_index("GJ/LIC/001") != before
