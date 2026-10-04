"""`X-Background-Refresh: 1` (the web app's 30-second polls) must not keep a session alive.

The session times out after 15 minutes without the user doing anything. Every ordinary request
extends it (SESSION_SAVE_EVERY_REQUEST); a background refresh still authenticates normally but
leaves the expiry where it was, so an open tab that only polls is still signed out on time.
"""

from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone

from identity.roles import Role
from tests.test_alerts_api import login

pytestmark = pytest.mark.django_db

BACKGROUND = {"HTTP_X_BACKGROUND_REFRESH": "1"}


@pytest.fixture
def signed_in(app_db, client, make_user, otp_outbox):
    login(client, make_user(role=Role.LICENSEE), otp_outbox)
    key = client.cookies[settings.SESSION_COOKIE_NAME].value
    # Pretend the user was last active a few minutes ago.
    earlier = timezone.now() + timedelta(minutes=5)
    Session.objects.filter(session_key=key).update(expire_date=earlier)
    return key, earlier


def expiry(key):
    return Session.objects.get(session_key=key).expire_date


def test_background_refresh_does_not_extend_the_session(client, signed_in):
    key, earlier = signed_in
    response = client.get("/api/auth/me", **BACKGROUND)
    assert response.status_code == 200
    assert settings.SESSION_COOKIE_NAME not in response.cookies
    assert expiry(key) == earlier


def test_an_ordinary_request_extends_the_session(client, signed_in):
    key, earlier = signed_in
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert settings.SESSION_COOKIE_NAME in response.cookies
    assert expiry(key) > earlier + timedelta(minutes=9)


def test_background_refresh_still_fails_once_the_session_expired(client, signed_in):
    key, _ = signed_in
    Session.objects.filter(session_key=key).update(
        expire_date=timezone.now() - timedelta(seconds=1)
    )
    assert client.get("/api/auth/me", **BACKGROUND).status_code == 403
