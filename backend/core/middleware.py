"""Run every request in a single transaction tagged with the acting user.

This replaces ATOMIC_REQUESTS so that the RLS context and the view's queries share
one transaction. Any 5xx response rolls back, so a crash never leaves half a change.
"""

from django.db import transaction

from core.db_context import set_actor


class DbContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with transaction.atomic():
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                set_actor(user_id=user.user_id, role=user.role)
            response = self.get_response(request)
            if response.status_code >= 500:
                transaction.set_rollback(True)
            return response
