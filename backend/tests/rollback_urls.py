"""Test-only URLconf for test_rollback_on_exception.py.

Exists only to exercise a view that writes an audit event and then raises, so the
test can assert the write rolls back with the exception (via @pytest.mark.urls).
"""

from django.urls import path
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from audit.service import record


class RollingBackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        record(action="test.should_roll_back")
        raise ValidationError("boom")


urlpatterns = [
    path("rollback", RollingBackView.as_view()),
]
