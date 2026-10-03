"""DRF exception handler: a raised exception rolls back the request's transaction.

Rule for every view: RAISE to roll back, RETURN a response to commit. (The login views
return 401 on failure on purpose, so lockout counters persist.)"""

from django.db import transaction
from rest_framework.views import exception_handler


def rollback_on_exception(exc, context):
    transaction.set_rollback(True)
    return exception_handler(exc, context)
