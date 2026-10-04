import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from identity.models import USER_ID_ALPHABET, User
from identity.roles import Role

pytestmark = pytest.mark.django_db


def test_user_id_is_system_generated(app_db, make_user):
    user = make_user()
    assert len(user.user_id) == 12
    assert user.user_id.startswith("GJ")
    assert all(ch in USER_ID_ALPHABET for ch in user.user_id[2:])


def test_user_ids_are_unique(app_db, make_user):
    assert make_user().user_id != make_user().user_id


def test_password_is_hashed_with_argon2(app_db, make_user):
    user = make_user(password="a-long-test-password")
    assert user.password.startswith("argon2")
    assert user.check_password("a-long-test-password")


def test_contact_is_encrypted_at_rest(app_db, make_user):
    user = make_user(contact="+919876543210")
    with connection.cursor() as cursor:
        cursor.execute("SELECT contact_encrypted FROM identity_user WHERE id = %s", [user.id])
        raw = cursor.fetchone()[0]
    assert "9876543210" not in raw
    assert User.objects.get(pk=user.pk).get_contact() == "+919876543210"


def test_database_rejects_unknown_role(app_db):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create(role="SUPERHERO", contact_encrypted="x")


def test_has_role(app_db, make_user):
    user = make_user(role=Role.LICENSEE)
    assert user.has_role(Role.LICENSEE, Role.PERSONNEL)
    assert not user.has_role(Role.PERSONNEL)


def test_inactive_user_has_no_role(app_db, make_user):
    user = make_user(role=Role.LICENSEE)
    user.is_active = False
    assert not user.has_role(Role.LICENSEE)


def test_app_role_cannot_delete_users(app_db, make_user):
    user = make_user()
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic():
            User.objects.filter(pk=user.pk).delete()
