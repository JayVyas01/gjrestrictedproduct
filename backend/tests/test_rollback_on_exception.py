"""A raised exception rolls back the request's writes.

DRF turns raised exceptions (ValidationError, PermissionDenied, NotFound, Throttled)
into 4xx responses inside the view. DRF's own set_rollback only acts under
ATOMIC_REQUESTS (which we don't use), so without core.exceptions.rollback_on_exception
a view that writes and then raises would commit half a change.
"""

import pytest

pytestmark = pytest.mark.django_db


@pytest.mark.urls("tests.rollback_urls")
def test_raised_exception_rolls_back_audit_write(app_db, client, audit_actions):
    response = client.post("/rollback", {}, content_type="application/json")
    assert response.status_code == 400
    assert "test.should_roll_back" not in audit_actions()
