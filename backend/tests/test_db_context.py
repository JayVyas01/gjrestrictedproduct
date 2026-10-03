import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.http import HttpResponse

from core.db_context import current_actor, set_actor
from core.middleware import DbContextMiddleware
from identity.models import User
from identity.roles import Role

pytestmark = pytest.mark.django_db


def test_set_actor_is_visible_to_postgres(app_db):
    set_actor(user_id="GJTESTUSER01", role=Role.LICENSEE)
    assert current_actor() == ("GJTESTUSER01", "LICENSEE")


def test_set_actor_refuses_to_run_outside_a_transaction(app_db, monkeypatch):
    monkeypatch.setattr(connection, "in_atomic_block", False)
    with pytest.raises(RuntimeError, match="transaction"):
        set_actor(user_id="GJTESTUSER01", role=Role.LICENSEE)


def test_middleware_tags_request_with_authenticated_user(app_db, rf, make_user):
    user = make_user(role=Role.LICENSEE)
    request = rf.get("/")
    request.user = user
    seen = {}

    def view(req):
        seen["actor"] = current_actor()
        return HttpResponse()

    DbContextMiddleware(view)(request)
    assert seen["actor"] == (user.user_id, "LICENSEE")


def test_middleware_sets_no_actor_for_anonymous_request(app_db, rf):
    request = rf.get("/")
    request.user = AnonymousUser()
    seen = {}

    def view(req):
        seen["actor"] = current_actor()
        return HttpResponse()

    DbContextMiddleware(view)(request)
    assert not any(seen["actor"])


def test_anonymous_request_after_authenticated_request_has_no_actor(app_db, rf, make_user):
    user = make_user(role=Role.LICENSEE)
    authenticated_request = rf.get("/")
    authenticated_request.user = user
    DbContextMiddleware(lambda req: HttpResponse())(authenticated_request)

    anonymous_request = rf.get("/")
    anonymous_request.user = AnonymousUser()
    seen = {}

    def view(req):
        seen["actor"] = current_actor()
        return HttpResponse()

    DbContextMiddleware(view)(anonymous_request)
    assert not any(seen["actor"])


def test_middleware_rolls_back_writes_on_server_error(app_db, rf, make_user):
    user = make_user()
    request = rf.get("/")
    request.user = user

    def failing_view(req):
        User.objects.filter(pk=user.pk).update(failed_login_count=3)
        return HttpResponse(status=500)

    DbContextMiddleware(failing_view)(request)
    user.refresh_from_db()
    assert user.failed_login_count == 0
