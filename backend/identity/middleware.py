"""The password-change gate (owner decision A3, 2026-10-06).

While a signed-in user's `must_change_password` is set (a password the system issued), every
API answers 403 with code `password_change_required`, except the few the web app needs to
show the change-password screen, change the password or sign out, and the anonymous ones.

A middleware rather than a DRF default permission: a default permission is replaced by every
view that sets its own `permission_classes` (all the role-checked views and the AllowAny ones),
so new endpoints could silently escape it. Here every `/api/` request is checked, whatever the
view, and the allow-list below is the only way past it.
"""

from django.http import JsonResponse

GATE_RESPONSE = {
    "detail": "Choose a new password before continuing.",
    "code": "password_change_required",
}

# Exact paths, then prefixes. Everything else under /api/ is gated.
ALLOWED_PATHS = frozenset(
    {
        "/api/auth/me",
        "/api/auth/password",
        "/api/auth/logout",
        "/api/auth/csrf",
        "/api/auth/login",
        "/api/auth/login/verify",
        "/api/health",
    }
)
ALLOWED_PREFIXES = ("/api/enrolment/", "/api/demo/")  # anonymous: enrolment and demo-only


def is_allowed(path: str) -> bool:
    return path in ALLOWED_PATHS or path.startswith(ALLOWED_PREFIXES)


class PasswordChangeGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if path.startswith("/api/") and not is_allowed(path):
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated and user.must_change_password:
                return JsonResponse(GATE_RESPONSE, status=403)
        return self.get_response(request)
