"""Request middleware: the per-request transaction and actor, and the session middleware.

DbContextMiddleware runs every request in a single transaction tagged with the acting user.

This replaces ATOMIC_REQUESTS so that the RLS context and the view's queries share
one transaction. Rule for every view: RAISE to roll back, RETURN a response to commit
(the login views return 401 on failure on purpose, so lockout counters persist); any
5xx response always rolls back.

Each request's transaction.atomic() is a savepoint inside the outer connection, and a
transaction-local GUC set inside a savepoint survives RELEASE SAVEPOINT (it is only
undone by ROLLBACK TO SAVEPOINT). So the actor must be set on every request, including
anonymous ones -- otherwise an anonymous request on a reused connection would inherit
the previous request's actor.
"""

from django.contrib.sessions.middleware import SessionMiddleware as DjangoSessionMiddleware
from django.db import transaction
from django.utils.cache import patch_vary_headers

from core.db_context import set_actor


class DbContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with transaction.atomic():
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                set_actor(user_id=user.user_id, role=user.role)
            else:
                set_actor(user_id="", role="")
            response = self.get_response(request)
            if response.status_code >= 500:
                transaction.set_rollback(True)
            return response


BACKGROUND_REFRESH_HEADER = "X-Background-Refresh"


class SessionMiddleware(DjangoSessionMiddleware):
    """Django's session middleware, except that a background refresh never extends the session.

    The session ends after SESSION_COOKIE_AGE without activity, and every request normally
    extends it (SESSION_SAVE_EVERY_REQUEST). The web app's 30-second polls (home counts, alerts)
    send `X-Background-Refresh: 1`: they authenticate as usual -- and fail once the session has
    expired -- but are not activity, so neither the stored expiry nor the cookie is renewed.
    A request that changed the session (signing in or out) is always saved.
    """

    def process_response(self, request, response):
        session = getattr(request, "session", None)
        if (
            session is not None
            and request.headers.get(BACKGROUND_REFRESH_HEADER) == "1"
            and not session.modified
        ):
            if session.accessed:
                patch_vary_headers(response, ("Cookie",))
            return response
        return super().process_response(request, response)
