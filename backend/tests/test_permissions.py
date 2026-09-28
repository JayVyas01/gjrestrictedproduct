import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from identity.permissions import role_required
from identity.roles import Role

pytestmark = pytest.mark.django_db


def probe_view(*roles):
    class Probe(APIView):
        permission_classes = [role_required(*roles)]

        def get(self, request):
            return Response({"ok": True})

    return Probe.as_view()


def call(view, user):
    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)
    return view(request)


def test_listed_role_is_allowed(app_db, make_user):
    view = probe_view(Role.HEAD_AUTHORITY)
    assert call(view, make_user(role=Role.HEAD_AUTHORITY)).status_code == 200


@pytest.mark.parametrize("role", [r for r in Role if r != Role.HEAD_AUTHORITY])
def test_every_other_role_is_refused(app_db, make_user, role):
    view = probe_view(Role.HEAD_AUTHORITY)
    assert call(view, make_user(role=role)).status_code == 403


def test_anonymous_is_refused(app_db):
    view = probe_view(Role.HEAD_AUTHORITY)
    assert call(view, AnonymousUser()).status_code == 403


def test_deactivated_user_is_refused(app_db, make_user):
    user = make_user(role=Role.HEAD_AUTHORITY)
    user.is_active = False
    assert call(probe_view(Role.HEAD_AUTHORITY), user).status_code == 403
