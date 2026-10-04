import pytest
from django.core.management import CommandError, call_command

from identity.models import User
from identity.roles import Role

pytestmark = pytest.mark.django_db

COMMAND_MODULE = "identity.management.commands.create_software_owner"


@pytest.fixture
def answers(monkeypatch):
    def _set(contact="+919822222222", password="a-strong-owner-pass-42", repeat=None):
        monkeypatch.setattr("builtins.input", lambda prompt: contact)
        replies = iter([password, repeat if repeat is not None else password])
        monkeypatch.setattr(f"{COMMAND_MODULE}.getpass.getpass", lambda prompt: next(replies))

    return _set


def test_creates_first_owner_and_audits_it(app_db, answers, capsys, audit_actions):
    answers()
    call_command("create_software_owner")
    owner = User.objects.get(role=Role.SOFTWARE_OWNER)
    assert owner.get_contact() == "+919822222222"
    assert owner.user_id in capsys.readouterr().out
    assert audit_actions() == ["account.bootstrap_owner_created"]


def test_refuses_when_an_owner_already_exists(app_db, answers, make_user):
    make_user(role=Role.SOFTWARE_OWNER)
    answers()
    with pytest.raises(CommandError, match="already exists"):
        call_command("create_software_owner")


def test_rejects_weak_password(app_db, answers):
    answers(password="short", repeat="short")
    with pytest.raises(CommandError):
        call_command("create_software_owner")
    assert not User.objects.exists()


def test_rejects_mismatched_passwords(app_db, answers):
    answers(repeat="something-else-entirely-9")
    with pytest.raises(CommandError, match="do not match"):
        call_command("create_software_owner")
