# Demo D2b — Buyer-Rejection Alerts and Superintendent Batch Sign-off Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two things:
1. **Buyer-rejection alerts.** When a buyer rejects a transaction, the designated officer's and superintendent's positions get an in-app alert. It shows the reason and a 30-day pattern signal, and the officer can acknowledge it.
2. **Periodic batches.** Superintendents get a batch of approved transactions for their district every 15, 30 or 60 days. They can flag individual transactions, which alerts the approving officer, and sign the batch off with a one-time code.

**Architecture:** Two new apps.
- **`alerts`:** alerts addressed to **positions**, plus acknowledgements.
- **`oversight`:** review-period settings, batches, batch items, flags and sign-offs.

**Rules shared with D2a:**
- **Writes:** every write runs in a service inside `acting_as_system(...)`, after a plain-Python check of who may act.
- **Reads:** row-level security limits reads to whoever currently holds the addressed position, plus Head Authority, Software Owner and SYSTEM.
- **Permanence:** all records are append-only, enforced by REVOKE plus the shared `reject_append_only_change()` triggers.
- **Batch locks:** batches are append-only, so the sign-off and flag paths serialise on a **transaction-scoped advisory lock per batch** rather than a row lock.

**Tech Stack:** Django 5.2, DRF 3.17, PostgreSQL 16, pytest-django.

**Spec:** [`2026-09-28-licence-types-and-demo-design.md`](../specs/2026-09-28-licence-types-and-demo-design.md) Revision 3 (D9, D11, §5a, §5b "Periodic oversight", §6 scenes 6a and the buyer-rejection scene). **Builds on:** D2a ([PR #5](https://github.com/JayVyas01/gjrestrictedproduct/pull/5)). This branch is stacked on `feature/demo-d2-transactions` until PR #5 is merged into `dev`. **Roadmap:** [`2026-09-26-roadmap.md`](2026-09-26-roadmap.md)

## Global Constraints

- All Phase 1, D1 and D2a constraints apply; see `docs/CODEMAP.md` section 4. In brief:
  - Raise to roll back, return to commit.
  - `record()` is the last lock taken. Audit payloads hold IDs and blind indexes only.
  - Tests use `app_db`, never `transactional_db`.
  - Append-only means REVOKE plus `reject_append_only_change()` triggers.
  - Row-level-security policies go in the migration that creates the table.
  - **Every task updates `docs/CODEMAP.md`.**
- **Lock order:**
  - Decisions (D2a): user row → OTP challenge rows → transaction row → stock rows (sorted) → **alert inserts** → audit.
  - Oversight: user row → OTP challenge rows → **batch advisory lock** → flag, alert or sign-off inserts → audit.
- **Alerts are addressed to positions, not people.** Whoever currently holds the position sees and acknowledges them, including after a transfer. Each alert has at most one acknowledgement.
- **Buyer-rejection alert recipients:** `tx.designated_position` and `tx.superintendent_position`, one alert each. Both are always set, which D2a guarantees.
- **Pattern signal:** the number of the seller's transactions with status `REJECTED_BY_BUYER` and `decided_at` within the last **30 days**, including this one. Shown as text, for example "3rd buyer rejection for this seller in the last 30 days".
- **Flag alert recipient:** the position recorded on the transaction's officer `APPROVE` decision row, which is the approving officer's position.
- **Review periods:**
  - **Allowed values:** `15`, `30` or `60` days, set **per district-level position** (the superintendent).
  - **Periods:** they start at the setting's `starts_on` and run back to back.
  - **When a batch is created:** only once its period has fully ended, meaning `period_end < today`.
  - **What a batch contains:** every transaction whose stored `superintendent_position` is that position, with status `APPROVED` and `decided_at` (local date, Asia/Kolkata) within the period.
- **Sign-off deadline:** `due_on = period_end + 30 days`.
  - **Status:** `SIGNED` once signed; `OVERDUE` when unsigned and today is after `due_on`; otherwise `OPEN`.
- **Sign-off** requires a fresh one-time code (purpose `DECISION`) from the superintendent who currently holds the position.
  - **Flagging:** only allowed while the batch is unsigned. A flag needs a `SUPERINTENDENT_FLAG` reason code ("Other" needs text), and a transaction can be flagged at most once per batch.
  - **Comments:** capped at 500 characters by the serializers.
- **Plain-language messages:** use the exact wording given in the tasks.
- **Out of scope:** screens (D3), automatic scheduling of `create_due_batches` and seed data (D4), report export and escalation of overdue batches (Phase 5).

## Review Focus

1. **The officer is transferred after an alert is raised.** The new holder must see and be able to acknowledge it; the old holder must not see it. Tested in Task 1 (`test_alert_follows_the_position_after_transfer`).
2. **A rejection older than 30 days** must not count towards the pattern signal. Tested in Task 1 (`test_pattern_ignores_rejections_older_than_30_days`).
3. **`create_due_batches` run twice, or after several missed periods,** must create each period's batch exactly once and none for the period still in progress. Tested in Task 3 (`test_batches_are_created_once_per_completed_period`).
4. **Flagging or signing off a batch that is already signed** must be refused with a plain message. Tested in Task 4 (`test_signed_batch_cannot_be_flagged_or_signed_again`).
5. **A wrong code at sign-off** must count the attempt and must not sign the batch. Tested in Task 4 (`test_wrong_code_does_not_sign`).

## File Structure

```
backend/
  alerts/models.py, service.py, presenters.py, views.py, urls.py, migrations/0001 (gen), 0002_rls_and_append_only.py
  oversight/models.py, service.py, presenters.py, serializers.py, views.py, urls.py
  oversight/migrations/0001 (gen), 0002_rls_and_append_only.py
  oversight/management/commands/create_due_batches.py
  transactions/models.py                 # + indexes
  transactions/migrations/0004_indexes.py (gen)
  transactions/service.py                # _apply raises buyer-rejection alerts
  tests/conftest.py                      # + settle, set_decided_on, review_setting fixtures
  tests/test_alerts.py, test_alerts_api.py, test_oversight_batches.py,
  tests/test_oversight_review.py, test_oversight_api.py
```

---

### Task 1: Alerts on buyer rejection

**Files:**
- Create: `backend/alerts/__init__.py`, `apps.py`, `models.py`, `service.py`, `migrations/__init__.py`
- Create (generated): `backend/alerts/migrations/0001_initial.py`
- Create: `backend/alerts/migrations/0002_rls_and_append_only.py`
- Modify:
  - `backend/transactions/models.py` (indexes)
  - `backend/transactions/service.py` (`_apply` hook)
  - `backend/config/settings.py`
  - `backend/tests/conftest.py`
  - `docs/CODEMAP.md`
- Create (generated): `backend/transactions/migrations/0004_indexes.py`
- Test: `backend/tests/test_alerts.py`

**Interfaces:**
- Consumes:
  - `transactions.models.Transaction`, `TransactionStatus`
  - `positions.service.positions_held`
  - `reasons.models.ReasonCode`
  - `acting_as_system`, `record`
- Produces:
  - `alerts.models.AlertKind` (`BUYER_REJECTION`, `SUPERINTENDENT_FLAG`)
  - `AuthorityAlert(kind, position, transaction, reason, comment, pattern_count, created_at)`
  - `AlertAcknowledgement(alert one-to-one, user_id, note, created_at)`
  - `alerts.service.NotAllowed(Exception)`
  - `alerts.service.PATTERN_WINDOW = timedelta(days=30)`
  - `alerts.service.ordinal(n: int) -> str`
  - `alerts.service.pattern_text(count: int) -> str`
  - `alerts.service.raise_buyer_rejection_alerts(tx, reason, comment) -> list[AuthorityAlert]` (SYSTEM context)
  - `alerts.service.raise_flag_alert(*, tx, position, reason, comment) -> AuthorityAlert` (SYSTEM context)
  - `alerts.service.acknowledge(*, alert_id: int, user: User, note: str = "") -> AlertAcknowledgement`
  - Conftest:
    - `settle(qty="10", *, buyer="CONFIRM", officer="APPROVE", reason_code="", comment="") -> Transaction`, which drives a transaction through the real services. Set `officer=None` to stop at `AWAITING_OFFICER`.
    - `set_decided_on(tx, day: date)`, which sets `decided_at` to noon local time on that day, as SYSTEM.

- [ ] **Step 1: Write the fixtures and failing tests**

Add to `backend/tests/conftest.py`, with the imports at the top of the file:
```python
from datetime import datetime, time  # alongside the existing datetime imports

from django.utils import timezone
from transactions.models import Transaction
from transactions.service import Transport, decide, request_decision_code, start_transaction

TEST_TRANSPORT = Transport(
    name="Ravi Transport Co", id_number="GJ-TR-4411", vehicle_number="GJ01AB1234", route="Sanand to Bopal"
)


def _sign(user, tx, outcome, otp_outbox, reason_code="", comment=""):
    set_actor(user_id=user.user_id, role=user.role)
    challenge = request_decision_code(reference=tx.reference, user=user)
    return decide(reference=tx.reference, user=user, challenge_id=str(challenge.public_id),
                  code=otp_outbox[-1][1], outcome=outcome, reason_code=reason_code, comment=comment)


@pytest.fixture
def settle(trade, catalogue, otp_outbox):
    """Drive a transaction through the real services: seller starts, buyer decides, officer decides."""

    def _settle(qty="10", *, buyer="CONFIRM", officer="APPROVE", reason_code="", comment=""):
        set_actor(user_id=trade.seller.user_id, role=trade.seller.role)
        tx = start_transaction(seller=trade.seller, buyer_gstin=BUYER_GSTIN, substance=catalogue.whisky,
                               quantity=Decimal(qty), transport=TEST_TRANSPORT)
        tx = _sign(trade.buyer, tx, buyer, otp_outbox,
                   reason_code=reason_code if buyer == "REJECT" else "", comment=comment if buyer == "REJECT" else "")
        if buyer == "CONFIRM" and officer:
            tx = _sign(trade.officer, tx, officer, otp_outbox,
                       reason_code=reason_code if officer == "REJECT" else "",
                       comment=comment if officer == "REJECT" else "")
        return tx

    return _settle


def set_decided_on(tx, day):
    """Move a settled transaction's decision time to noon (local) on `day` — for period tests."""
    moment = timezone.make_aware(datetime.combine(day, time(12, 0)))
    with acting_as_system("test"):
        Transaction.objects.filter(pk=tx.pk).update(decided_at=moment)
```
`set_actor` and `acting_as_system` are already imported in conftest. If they aren't, import them from `core.db_context`.

`backend/tests/test_alerts.py`:
```python
from datetime import timedelta

import pytest
from django.db import DatabaseError, transaction
from django.utils import timezone

from alerts.models import AlertAcknowledgement, AuthorityAlert
from alerts.service import NotAllowed, acknowledge, ordinal, pattern_text
from core.db_context import acting_as_system, set_actor
from identity.roles import Role
from positions.service import assign
from transactions.models import Transaction

pytestmark = pytest.mark.django_db


def visible_alerts(user):
    with transaction.atomic():
        set_actor(user_id=user.user_id, role=user.role)
        return list(AuthorityAlert.objects.order_by("id"))


@pytest.mark.parametrize(("n", "text"), [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"),
                                         (12, "12th"), (13, "13th"), (21, "21st"), (22, "22nd"), (103, "103rd")])
def test_ordinal(n, text):
    assert ordinal(n) == text


def test_pattern_text():
    assert pattern_text(3) == "3rd buyer rejection for this seller in the last 30 days"


def test_buyer_rejection_alerts_officer_and_superintendent(app_db, org, trade, settle, audit_actions):
    tx = settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        alerts = list(AuthorityAlert.objects.filter(transaction=tx).order_by("id"))
    assert [a.position for a in alerts] == [org.area_officer, org.district_officer]
    assert {a.kind for a in alerts} == {"BUYER_REJECTION"}
    assert alerts[0].reason.code == "NOT_ORDERED" and alerts[0].pattern_count == 1
    assert audit_actions()[-1] == "transaction.buyer_rejected"


def test_buyer_comment_is_kept_on_the_alert(app_db, trade, settle):
    tx = settle(buyer="REJECT", reason_code="OTHER", comment="Never ordered from them")
    with acting_as_system("test"):
        assert AuthorityAlert.objects.filter(transaction=tx).first().comment == "Never ordered from them"


def test_confirm_and_officer_reject_raise_no_alerts(app_db, trade, settle):
    settle()
    settle(officer="REJECT", reason_code="QUANTITY_MISMATCH")
    with acting_as_system("test"):
        assert AuthorityAlert.objects.count() == 0


def test_pattern_counts_recent_rejections(app_db, trade, settle):
    for _ in range(3):
        last = settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        assert AuthorityAlert.objects.filter(transaction=last).first().pattern_count == 3


def test_pattern_ignores_rejections_older_than_30_days(app_db, trade, settle):
    old = settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        Transaction.objects.filter(pk=old.pk).update(decided_at=timezone.now() - timedelta(days=31))
    recent = settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        assert AuthorityAlert.objects.filter(transaction=recent).first().pattern_count == 1


def test_only_position_holders_and_authorities_see_alerts(app_db, trade, settle, make_user):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    head = make_user(role=Role.HEAD_AUTHORITY)
    stranger = make_user(role=Role.PERSONNEL)
    assert len(visible_alerts(trade.officer)) == 1
    assert len(visible_alerts(trade.superintendent)) == 1
    assert len(visible_alerts(head)) == 2
    assert visible_alerts(trade.seller) == visible_alerts(trade.buyer) == visible_alerts(stranger) == []


def test_alert_follows_the_position_after_transfer(app_db, org, trade, settle, make_user, audit_actions):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    replacement = make_user(role=Role.PERSONNEL)
    assign(org.area_officer, replacement, by="test")
    assert visible_alerts(trade.officer) == []
    [alert] = visible_alerts(replacement)
    set_actor(user_id=replacement.user_id, role=replacement.role)
    ack = acknowledge(alert_id=alert.id, user=replacement, note="Called the buyer")
    assert ack.user_id == replacement.user_id
    assert audit_actions()[-1] == "alert.acknowledged"


def test_acknowledge_rules(app_db, trade, settle):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    [officer_alert] = visible_alerts(trade.officer)
    set_actor(user_id=trade.superintendent.user_id, role=trade.superintendent.role)
    with pytest.raises(NotAllowed, match="Only the officer holding this position"):
        acknowledge(alert_id=officer_alert.id, user=trade.superintendent)
    set_actor(user_id=trade.officer.user_id, role=trade.officer.role)
    acknowledge(alert_id=officer_alert.id, user=trade.officer)
    with pytest.raises(NotAllowed, match="already acknowledged"):
        acknowledge(alert_id=officer_alert.id, user=trade.officer)


def test_alerts_and_acknowledgements_are_append_only_even_for_owner(db, trade, settle):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    with acting_as_system("test"):
        alert = AuthorityAlert.objects.first()
        AlertAcknowledgement.objects.create(alert=alert, user_id="x")
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            AuthorityAlert.objects.update(comment="edited")
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            AlertAcknowledgement.objects.update(note="edited")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_alerts.py -v`
Expected: collection error, `No module named 'alerts'`.

- [ ] **Step 3: Write the app**

`backend/alerts/__init__.py` and `backend/alerts/migrations/__init__.py` are empty.

`backend/alerts/apps.py`:
```python
from django.apps import AppConfig


class AlertsConfig(AppConfig):
    name = "alerts"
```

`backend/alerts/models.py`:
```python
"""In-app alerts for authorities, addressed to POSITIONS (whoever holds the position sees it).

Raised when a buyer rejects a transaction (to the designated officer and the superintendent)
and when a superintendent flags an approved transaction (to the approving officer's position).
Alerts and acknowledgements are append-only.
"""

from django.db import models

from positions.models import Position
from reasons.models import ReasonCode
from transactions.models import Transaction


class AlertKind(models.TextChoices):
    BUYER_REJECTION = "BUYER_REJECTION", "Buyer rejected a transaction"
    SUPERINTENDENT_FLAG = "SUPERINTENDENT_FLAG", "Superintendent flagged a transaction"


class AuthorityAlert(models.Model):
    kind = models.CharField(max_length=24, choices=AlertKind.choices)
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="+")
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="alerts")
    reason = models.ForeignKey(ReasonCode, on_delete=models.PROTECT)
    comment = models.TextField(blank=True)
    pattern_count = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(kind__in=AlertKind.values), name="alert_kind_valid"),
        ]


class AlertAcknowledgement(models.Model):
    alert = models.OneToOneField(AuthorityAlert, on_delete=models.PROTECT, related_name="acknowledgement")
    user_id = models.CharField(max_length=12)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

`backend/alerts/service.py`:
```python
"""Raise and acknowledge authority alerts.

raise_* run inside the caller's SYSTEM block (decision or flag), before its audit record().
acknowledge checks in plain Python that the user currently holds the addressed position.
"""

from datetime import timedelta

from django.utils import timezone

from alerts.models import AlertAcknowledgement, AlertKind, AuthorityAlert
from audit.service import record
from core.db_context import acting_as_system
from identity.models import User
from positions.models import Position
from positions.service import positions_held
from reasons.models import ReasonCode
from transactions.models import Transaction, TransactionStatus

PATTERN_WINDOW = timedelta(days=30)


class NotAllowed(Exception):
    pass


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def pattern_text(count: int) -> str:
    return f"{ordinal(count)} buyer rejection for this seller in the last 30 days"


def _recent_rejections(tx: Transaction) -> int:
    return Transaction.objects.filter(
        seller_gstin_index=tx.seller_gstin_index,
        status=TransactionStatus.REJECTED_BY_BUYER,
        decided_at__gte=timezone.now() - PATTERN_WINDOW,
    ).count()


def raise_buyer_rejection_alerts(tx: Transaction, reason: ReasonCode, comment: str) -> list[AuthorityAlert]:
    count = _recent_rejections(tx)
    return [
        AuthorityAlert.objects.create(kind=AlertKind.BUYER_REJECTION, position=position, transaction=tx,
                                      reason=reason, comment=comment, pattern_count=count)
        for position in (tx.designated_position, tx.superintendent_position)
    ]


def raise_flag_alert(*, tx: Transaction, position: Position, reason: ReasonCode, comment: str) -> AuthorityAlert:
    return AuthorityAlert.objects.create(kind=AlertKind.SUPERINTENDENT_FLAG, position=position,
                                         transaction=tx, reason=reason, comment=comment)


def acknowledge(*, alert_id: int, user: User, note: str = "") -> AlertAcknowledgement:
    alert = AuthorityAlert.objects.select_related("position").filter(pk=alert_id).first()
    if alert is None or alert.position not in positions_held(user):
        raise NotAllowed("Only the officer holding this position can acknowledge this alert.")
    with acting_as_system("acknowledge_alert"):
        if AlertAcknowledgement.objects.filter(alert=alert).exists():
            raise NotAllowed("This alert is already acknowledged.")
        ack = AlertAcknowledgement.objects.create(alert=alert, user_id=user.user_id, note=note.strip())
        record(action="alert.acknowledged", actor=user.user_id, subject_type="alert", subject_id=str(alert.id))
    return ack
```

Add `"alerts",` to `INSTALLED_APPS` after `"transactions",`, then generate `alerts` 0001.

`backend/alerts/migrations/0002_rls_and_append_only.py`:
```python
"""Alerts are visible to whoever currently holds the addressed position, and to Head Authority,
Software Owner and SYSTEM. Only SYSTEM writes. Alerts and acknowledgements are append-only."""

from django.db import migrations

ROLE = "current_setting('app.role', true)"
HELD = (
    "(SELECT a.position_id FROM positions_personnelassignment a "
    "JOIN identity_user u ON u.id = a.user_id "
    "WHERE u.user_id = current_setting('app.user_id', true) AND a.ended_at IS NULL)"
)
READERS = "('HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'SYSTEM')"

FORWARD = f"""
ALTER TABLE alerts_authorityalert ENABLE ROW LEVEL SECURITY;
CREATE POLICY alert_read ON alerts_authorityalert FOR SELECT TO gj_app
    USING (position_id IN {HELD} OR {ROLE} IN {READERS});
CREATE POLICY alert_insert ON alerts_authorityalert FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON alerts_authorityalert FROM gj_app;
CREATE TRIGGER alert_no_update_delete BEFORE UPDATE OR DELETE ON alerts_authorityalert
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER alert_no_truncate BEFORE TRUNCATE ON alerts_authorityalert
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();

ALTER TABLE alerts_alertacknowledgement ENABLE ROW LEVEL SECURITY;
CREATE POLICY ack_read ON alerts_alertacknowledgement FOR SELECT TO gj_app
    USING (alert_id IN (SELECT id FROM alerts_authorityalert));
CREATE POLICY ack_insert ON alerts_alertacknowledgement FOR INSERT TO gj_app
    WITH CHECK ({ROLE} = 'SYSTEM');
REVOKE UPDATE, DELETE, TRUNCATE ON alerts_alertacknowledgement FROM gj_app;
CREATE TRIGGER ack_no_update_delete BEFORE UPDATE OR DELETE ON alerts_alertacknowledgement
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER ack_no_truncate BEFORE TRUNCATE ON alerts_alertacknowledgement
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();
"""  # noqa: S608 - SQL built only from the constants above; no user input.

BACKWARD = """
DROP TRIGGER ack_no_truncate ON alerts_alertacknowledgement;
DROP TRIGGER ack_no_update_delete ON alerts_alertacknowledgement;
DROP POLICY ack_insert ON alerts_alertacknowledgement;
DROP POLICY ack_read ON alerts_alertacknowledgement;
ALTER TABLE alerts_alertacknowledgement DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON alerts_alertacknowledgement TO gj_app;
DROP TRIGGER alert_no_truncate ON alerts_authorityalert;
DROP TRIGGER alert_no_update_delete ON alerts_authorityalert;
DROP POLICY alert_insert ON alerts_authorityalert;
DROP POLICY alert_read ON alerts_authorityalert;
ALTER TABLE alerts_authorityalert DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON alerts_authorityalert TO gj_app;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("alerts", "0001_initial"),
        ("positions", "0002_one_position_per_area"),
        ("identity", "0009_otp_purpose_decision"),
        ("core", "0002_append_only_guard"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
```
Place `# noqa: S608` the way ruff accepts it, as in earlier migrations. If ruff doesn't flag the line, remove the comment.

- [ ] **Step 4: Add the transaction indexes and the hook**

In `backend/transactions/models.py`, add to `Transaction.Meta`:
```python
        indexes = [
            models.Index(fields=["seller_gstin_index", "status", "decided_at"], name="tx_seller_status_decided"),
            models.Index(fields=["buyer_gstin_index"], name="tx_buyer"),
            models.Index(fields=["superintendent_position", "status", "decided_at"], name="tx_super_status_decided"),
        ]
```
Then run `makemigrations transactions --name indexes`.

In `backend/transactions/service.py` `_apply`, after the `TransactionDecision.objects.create(...)` call and **before** `record(...)`:
```python
    if role == "buyer" and outcome == DecisionOutcome.REJECT:
        raise_buyer_rejection_alerts(locked, reason, comment.strip())
```
Import it with `from alerts.service import raise_buyer_rejection_alerts`. The `alerts` app imports only `transactions.models`, never `transactions.service`, so there's no import cycle.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass, including every D2a test.

- [ ] **Step 6: Update CODEMAP and commit**

`docs/CODEMAP.md` changes:
- New `### alerts` section: models, service and migrations.
- Roles table:
  - Authorised Personnel: sees and acknowledges alerts for the positions they currently hold.
  - Head Authority and Software Owner: read all alerts.
- Section 4: the lock-order row now includes alert inserts.
- Fixtures row: `settle` and `set_decided_on`.
- Add the new tests and update the count.

```bash
uv run ruff format . && uv run ruff check . && uv run --env-file .env.test python manage.py makemigrations --check --dry-run
git add alerts/ transactions/ config/ tests/conftest.py tests/test_alerts.py ../docs/CODEMAP.md
git commit -m "feat: buyer-rejection alerts to the designated officer and superintendent positions"
```

---

### Task 2: Alerts API

**Files:**
- Create: `backend/alerts/presenters.py`, `views.py`, `urls.py`
- Modify: `backend/config/urls.py`, `docs/CODEMAP.md`
- Test: `backend/tests/test_alerts_api.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `alerts.presenters.alert_view(alert: AuthorityAlert) -> dict`, with keys `id`, `kind`, `kind_label`, `created_at`, `transaction_reference`, `substance`, `quantity`, `unit`, `seller_name`, `buyer_name`, `reason`, `comment`, `pattern`, `acknowledged`, `acknowledged_by`, `acknowledged_at` and `note`
  - `GET /api/alerts` (any logged-in user) returns 200 `{"unacknowledged": int, "alerts": [alert_view]}`. Unacknowledged alerts come first, then newest first, at most 100.
  - `POST /api/alerts/<id>/acknowledge` with `{note?}` returns 200 with the `alert_view`, or 403 `{detail}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_alerts_api.py`:
```python
import pytest

from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db


def login(client, user, otp_outbox):
    client.logout()
    first = client.post("/api/auth/login", {"user_id": user.user_id, "password": TEST_PASSWORD},
                        content_type="application/json")
    client.post("/api/auth/login/verify", {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
                content_type="application/json")


def test_officer_sees_alert_with_pattern(app_db, client, trade, settle, otp_outbox):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    login(client, trade.officer, otp_outbox)
    body = client.get("/api/alerts").json()
    assert body["unacknowledged"] == 1
    alert = body["alerts"][0]
    assert alert["kind"] == "BUYER_REJECTION"
    assert alert["reason"] == "I did not place this order"
    assert alert["pattern"] == "1st buyer rejection for this seller in the last 30 days"
    assert alert["seller_name"] == "Sanand Spirits Pvt Ltd" and alert["buyer_name"] == "Bopal Bar & Kitchen"
    assert alert["acknowledged"] is False
    assert "GJ/TEST" not in str(alert)


def test_acknowledge_over_http(app_db, client, trade, settle, otp_outbox):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    login(client, trade.officer, otp_outbox)
    alert_id = client.get("/api/alerts").json()["alerts"][0]["id"]
    acked = client.post(f"/api/alerts/{alert_id}/acknowledge", {"note": "Called the buyer"},
                        content_type="application/json").json()
    assert acked["acknowledged"] is True and acked["note"] == "Called the buyer"
    assert acked["acknowledged_by"] == trade.officer.user_id
    assert client.get("/api/alerts").json()["unacknowledged"] == 0


def test_licensees_see_no_alerts(app_db, client, trade, settle, otp_outbox):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    login(client, trade.seller, otp_outbox)
    assert client.get("/api/alerts").json() == {"unacknowledged": 0, "alerts": []}


def test_cannot_acknowledge_someone_elses_alert(app_db, client, trade, settle, otp_outbox):
    settle(buyer="REJECT", reason_code="NOT_ORDERED")
    login(client, trade.officer, otp_outbox)
    officer_alert = client.get("/api/alerts").json()["alerts"][0]["id"]
    login(client, trade.superintendent, otp_outbox)
    response = client.post(f"/api/alerts/{officer_alert}/acknowledge", {}, content_type="application/json")
    assert response.status_code == 403
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_alerts_api.py -v`
Expected: 404 on `/api/alerts`.

- [ ] **Step 3: Write the presenters, views and URLs**

`backend/alerts/presenters.py`:
```python
"""What an authority sees for an alert. Party names are read as SYSTEM (registered names only);
no licence numbers, GSTINs or contacts are ever included."""

from alerts.models import AlertKind, AuthorityAlert
from alerts.service import pattern_text
from core.db_context import acting_as_system
from transactions.checks import fmt_qty


def alert_view(alert: AuthorityAlert) -> dict:
    tx = alert.transaction
    with acting_as_system("alert_view"):
        seller_name, buyer_name = tx.seller_licence.holder_name, tx.buyer_licence.holder_name
    ack = getattr(alert, "acknowledgement", None)
    return {
        "id": alert.id, "kind": alert.kind, "kind_label": alert.get_kind_display(),
        "created_at": alert.created_at.isoformat(), "transaction_reference": tx.reference,
        "substance": tx.substance.name, "quantity": fmt_qty(tx.quantity), "unit": tx.unit,
        "seller_name": seller_name, "buyer_name": buyer_name, "reason": alert.reason.label,
        "comment": alert.comment or None,
        "pattern": pattern_text(alert.pattern_count) if alert.kind == AlertKind.BUYER_REJECTION else None,
        "acknowledged": ack is not None, "acknowledged_by": ack.user_id if ack else None,
        "acknowledged_at": ack.created_at.isoformat() if ack else None, "note": (ack.note or None) if ack else None,
    }
```
`getattr(alert, "acknowledgement", None)` raises `RelatedObjectDoesNotExist` when there is no row, which is a subclass of `AttributeError`, so `getattr`'s default applies. Keep it.

`backend/alerts/views.py`:
```python
"""Alert list and acknowledgement. Row-level security limits the list to positions the caller holds."""

from django.db.models import Exists, OuterRef
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from alerts.models import AlertAcknowledgement, AuthorityAlert
from alerts.presenters import alert_view
from alerts.service import NotAllowed, acknowledge


class AlertListView(APIView):
    def get(self, request):
        acked = AlertAcknowledgement.objects.filter(alert=OuterRef("pk"))
        rows = (
            AuthorityAlert.objects.select_related("transaction__substance", "reason")
            .annotate(is_acked=Exists(acked))
            .order_by("is_acked", "-created_at")[:100]
        )
        views = [alert_view(a) for a in rows]
        return Response({"unacknowledged": sum(not v["acknowledged"] for v in views), "alerts": views})


class AcknowledgeView(APIView):
    def post(self, request, alert_id):
        try:
            acknowledge(alert_id=alert_id, user=request.user, note=str(request.data.get("note", ""))[:500])
        except NotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        alert = AuthorityAlert.objects.select_related("transaction__substance", "reason").get(pk=alert_id)
        return Response(alert_view(alert))
```

`backend/alerts/urls.py`:
```python
from django.urls import path

from alerts import views

urlpatterns = [
    path("alerts", views.AlertListView.as_view()),
    path("alerts/<int:alert_id>/acknowledge", views.AcknowledgeView.as_view()),
]
```
Add `path("api/", include("alerts.urls")),` to `config/urls.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: Update CODEMAP and commit**

In `docs/CODEMAP.md`:
- Add rows for the alerts presenters, views and urls, and add the routes to the `config/urls.py` row.
- Add the new tests and update the count.

```bash
uv run ruff format . && uv run ruff check .
git add alerts/ config/ tests/test_alerts_api.py ../docs/CODEMAP.md
git commit -m "feat: alerts API with pattern signal and acknowledgement"
```

---

### Task 3: Review periods and batch creation

**Files:**
- Create: `backend/oversight/__init__.py`, `apps.py`, `models.py`, `service.py`, `migrations/__init__.py`
- Create: `backend/oversight/management/__init__.py`, `management/commands/__init__.py`, `management/commands/create_due_batches.py`
- Create (generated): `backend/oversight/migrations/0001_initial.py`
- Create: `backend/oversight/migrations/0002_rls_and_append_only.py`
- Modify: `backend/config/settings.py`, `backend/tests/conftest.py`, `docs/CODEMAP.md`
- Test: `backend/tests/test_oversight_batches.py`

**Interfaces:**
- Consumes:
  - `Transaction`, `TransactionStatus`
  - `positions.models.Position`, `AreaLevel`
  - `acting_as_system`, `record`
  - the `settle` and `set_decided_on` fixtures
- Produces:
  - Constants: `oversight.models.REVIEW_PERIODS = (15, 30, 60)` and `SIGN_OFF_DAYS = 30`
  - `SuperintendentSetting(position one-to-one, period_days, starts_on, updated_at, updated_by)`
  - `OversightBatch(position, period_start, period_end, created_at)` with method `due_on() -> date`
  - `BatchItem(batch, transaction)`
  - `oversight.service.InvalidSetting(Exception)`
  - `oversight.service.set_review_period(*, position: Position, days: int, by: str, starts_on: date | None = None) -> SuperintendentSetting`
  - `oversight.service.create_due_batches(today: date) -> list[OversightBatch]` (SYSTEM context)
  - Command: `manage.py create_due_batches [--today YYYY-MM-DD]`
  - Conftest fixture: `review_setting`, a 15-day period starting 2026-06-01 for `org.district_officer`

- [ ] **Step 1: Write the fixture and failing tests**

Add to `backend/tests/conftest.py`, with the import at the top of the file:
```python
from oversight.service import set_review_period


@pytest.fixture
def review_setting(org):
    with acting_as_system("test"):
        return set_review_period(position=org.district_officer, days=15, by="test", starts_on=date(2026, 6, 1))
```

`backend/tests/test_oversight_batches.py`:
```python
from datetime import date

import pytest
from django.core.management import call_command
from django.db import DatabaseError, transaction

from core.db_context import acting_as_system, set_actor
from identity.roles import Role
from oversight.models import BatchItem, OversightBatch
from oversight.service import InvalidSetting, create_due_batches, set_review_period
from tests.conftest import set_decided_on

pytestmark = pytest.mark.django_db


def run(today):
    with acting_as_system("test"):
        return create_due_batches(today)


def test_review_period_must_be_15_30_or_60_days(app_db, org):
    with acting_as_system("test"):
        with pytest.raises(InvalidSetting, match="15, 30 or 60"):
            set_review_period(position=org.district_officer, days=20, by="test")


def test_review_period_only_for_district_positions(app_db, org):
    with acting_as_system("test"):
        with pytest.raises(InvalidSetting, match="district"):
            set_review_period(position=org.area_officer, days=15, by="test")


def test_batch_holds_approved_transactions_of_the_period(app_db, org, settle, review_setting):
    inside = settle()
    set_decided_on(inside, date(2026, 6, 10))
    outside = settle()
    set_decided_on(outside, date(2026, 6, 20))
    rejected = settle(officer="REJECT", reason_code="QUANTITY_MISMATCH")
    set_decided_on(rejected, date(2026, 6, 10))
    [batch] = run(date(2026, 6, 16))
    assert (batch.period_start, batch.period_end) == (date(2026, 6, 1), date(2026, 6, 15))
    assert batch.position == org.district_officer
    assert batch.due_on() == date(2026, 7, 15)
    with acting_as_system("test"):
        assert [i.transaction_id for i in BatchItem.objects.filter(batch=batch)] == [inside.id]


def test_no_batch_for_the_period_still_running(app_db, settle, review_setting):
    assert run(date(2026, 6, 15)) == []


def test_batches_are_created_once_per_completed_period(app_db, settle, review_setting, audit_actions):
    created = run(date(2026, 7, 20))
    assert [(b.period_start, b.period_end) for b in created] == [
        (date(2026, 6, 1), date(2026, 6, 15)),
        (date(2026, 6, 16), date(2026, 6, 30)),
        (date(2026, 7, 1), date(2026, 7, 15)),
    ]
    assert run(date(2026, 7, 20)) == []
    assert audit_actions().count("oversight.batch_created") == 3


def test_empty_period_still_gets_a_batch(app_db, review_setting):
    [batch] = run(date(2026, 6, 16))
    with acting_as_system("test"):
        assert BatchItem.objects.filter(batch=batch).count() == 0


def test_changing_the_period_continues_after_the_last_batch(app_db, org, review_setting):
    run(date(2026, 6, 16))
    with acting_as_system("test"):
        setting = set_review_period(position=org.district_officer, days=30, by="test")
    assert setting.starts_on == date(2026, 6, 16)
    [batch] = run(date(2026, 7, 16))
    assert (batch.period_start, batch.period_end) == (date(2026, 6, 16), date(2026, 7, 15))


def test_only_the_superintendent_and_authorities_see_batches(app_db, trade, settle, review_setting, make_user):
    run(date(2026, 6, 16))
    head = make_user(role=Role.HEAD_AUTHORITY)
    def count(user):
        with transaction.atomic():
            set_actor(user_id=user.user_id, role=user.role)
            return OversightBatch.objects.count()
    assert count(trade.superintendent) == 1
    assert count(head) == 1
    assert count(trade.officer) == count(trade.seller) == 0


def test_batches_are_append_only_even_for_owner(db, review_setting):
    run(date(2026, 6, 16))
    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            OversightBatch.objects.update(period_end=date(2030, 1, 1))


def test_command_creates_due_batches(app_db, review_setting, capsys):
    call_command("create_due_batches", "--today", "2026-06-16")
    assert "Created 1 batch" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_oversight_batches.py -v`
Expected: collection error, `No module named 'oversight'`.

- [ ] **Step 3: Write the app**

The empty files: `backend/oversight/__init__.py`, `migrations/__init__.py`, `management/__init__.py`, `management/commands/__init__.py`.

`backend/oversight/apps.py`:
```python
from django.apps import AppConfig


class OversightConfig(AppConfig):
    name = "oversight"
```

`backend/oversight/models.py`:
```python
"""Periodic superintendent oversight: review-period settings, batches of approved transactions,
flags and sign-offs. Batches, items, flags and sign-offs are append-only; the setting is
configuration (changed only through set_review_period, which audits every change)."""

from datetime import date, timedelta

from django.db import models

from positions.models import Position
from transactions.models import Transaction

REVIEW_PERIODS = (15, 30, 60)
SIGN_OFF_DAYS = 30


class SuperintendentSetting(models.Model):
    position = models.OneToOneField(Position, on_delete=models.PROTECT, related_name="review_setting")
    period_days = models.PositiveSmallIntegerField()
    starts_on = models.DateField()
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(period_days__in=REVIEW_PERIODS), name="review_period_valid"),
        ]


class OversightBatch(models.Model):
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="batches")
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["position", "period_start"], name="one_batch_per_period"),
            models.CheckConstraint(condition=models.Q(period_end__gte=models.F("period_start")),
                                   name="batch_period_ordered"),
        ]

    def due_on(self) -> date:
        return self.period_end + timedelta(days=SIGN_OFF_DAYS)


class BatchItem(models.Model):
    batch = models.ForeignKey(OversightBatch, on_delete=models.PROTECT, related_name="items")
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["batch", "transaction"], name="one_item_per_transaction")]
```

`backend/oversight/service.py`:
```python
"""Review periods and batch creation (SYSTEM context).

Periods start at the setting's starts_on and run back to back. A batch is created only once
its period has fully ended (period_end < today) and lists every APPROVED transaction whose
superintendent position it is, decided (local date) within the period. Idempotent.
"""

from datetime import date, timedelta

from django.utils import timezone

from audit.service import record
from oversight.models import REVIEW_PERIODS, BatchItem, OversightBatch, SuperintendentSetting
from positions.models import AreaLevel, Position
from transactions.models import Transaction, TransactionStatus


class InvalidSetting(Exception):
    pass


def _next_start(position: Position, fallback: date) -> date:
    last = position.batches.order_by("-period_end").first()
    return last.period_end + timedelta(days=1) if last else fallback


def set_review_period(*, position: Position, days: int, by: str, starts_on: date | None = None) -> SuperintendentSetting:
    if days not in REVIEW_PERIODS:
        raise InvalidSetting("The review period must be 15, 30 or 60 days.")
    if position.area.level != AreaLevel.DISTRICT:
        raise InvalidSetting("Review periods can only be set for a district superintendent position.")
    start = starts_on or _next_start(position, timezone.localdate())
    setting, _ = SuperintendentSetting.objects.update_or_create(
        position=position, defaults={"period_days": days, "starts_on": start, "updated_by": by}
    )
    record(action="oversight.review_period_set", actor=by, subject_type="position", subject_id=position.code,
           payload={"period_days": days, "starts_on": start.isoformat()})
    return setting


def _make_batch(position: Position, start: date, end: date) -> OversightBatch:
    batch = OversightBatch.objects.create(position=position, period_start=start, period_end=end)
    approved = Transaction.objects.filter(
        superintendent_position=position, status=TransactionStatus.APPROVED,
        decided_at__date__gte=start, decided_at__date__lte=end,
    ).order_by("id")
    BatchItem.objects.bulk_create([BatchItem(batch=batch, transaction=tx) for tx in approved])
    record(action="oversight.batch_created", actor="create_due_batches", subject_type="batch",
           subject_id=str(batch.id), payload={"items": len(approved)})
    return batch


def create_due_batches(today: date) -> list[OversightBatch]:
    created = []
    for setting in SuperintendentSetting.objects.select_related("position").order_by("id"):
        start = max(_next_start(setting.position, setting.starts_on), setting.starts_on)
        while (end := start + timedelta(days=setting.period_days - 1)) < today:
            created.append(_make_batch(setting.position, start, end))
            start = end + timedelta(days=1)
    return created
```
`len(approved)` evaluates the queryset once. `bulk_create` takes the list made from it, so there is no second query.

`backend/oversight/management/commands/create_due_batches.py`:
```python
"""Create superintendent batches for every completed review period. Safe to run daily (idempotent)."""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.db_context import acting_as_system
from oversight.service import create_due_batches


class Command(BaseCommand):
    help = "Create oversight batches for review periods that have ended."

    def add_arguments(self, parser):
        parser.add_argument("--today", type=date.fromisoformat, default=None)

    def handle(self, *args, **options):
        today = options["today"] or timezone.localdate()
        with transaction.atomic(), acting_as_system("create_due_batches"):
            created = create_due_batches(today)
        self.stdout.write(f"Created {len(created)} batch(es)")
```

Add `"oversight",` to `INSTALLED_APPS` after `"alerts",`, then generate `oversight` 0001.

`backend/oversight/migrations/0002_rls_and_append_only.py`. This task covers batches and items; Task 4 adds flags and sign-offs in 0003.
```python
"""Batches are visible to whoever currently holds the batch's (superintendent) position and to
Head Authority, Software Owner and SYSTEM. Only SYSTEM writes. Batches and items are
append-only. The review setting is configuration without RLS (like positions; written only
through set_review_period, which is audited)."""

from django.db import migrations

ROLE = "current_setting('app.role', true)"
HELD = (
    "(SELECT a.position_id FROM positions_personnelassignment a "
    "JOIN identity_user u ON u.id = a.user_id "
    "WHERE u.user_id = current_setting('app.user_id', true) AND a.ended_at IS NULL)"
)
READERS = "('HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'SYSTEM')"


def _append_only(table: str, prefix: str) -> str:
    return f"""
REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM gj_app;
CREATE TRIGGER {prefix}_no_update_delete BEFORE UPDATE OR DELETE ON {table}
    FOR EACH ROW EXECUTE FUNCTION reject_append_only_change();
CREATE TRIGGER {prefix}_no_truncate BEFORE TRUNCATE ON {table}
    FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_change();
"""


FORWARD = f"""
ALTER TABLE oversight_oversightbatch ENABLE ROW LEVEL SECURITY;
CREATE POLICY batch_read ON oversight_oversightbatch FOR SELECT TO gj_app
    USING (position_id IN {HELD} OR {ROLE} IN {READERS});
CREATE POLICY batch_insert ON oversight_oversightbatch FOR INSERT TO gj_app WITH CHECK ({ROLE} = 'SYSTEM');
{_append_only("oversight_oversightbatch", "batch")}
ALTER TABLE oversight_batchitem ENABLE ROW LEVEL SECURITY;
CREATE POLICY item_read ON oversight_batchitem FOR SELECT TO gj_app
    USING (batch_id IN (SELECT id FROM oversight_oversightbatch));
CREATE POLICY item_insert ON oversight_batchitem FOR INSERT TO gj_app WITH CHECK ({ROLE} = 'SYSTEM');
{_append_only("oversight_batchitem", "item")}
"""  # noqa: S608 - SQL built only from constants; no user input.

BACKWARD = """
DROP TRIGGER item_no_truncate ON oversight_batchitem;
DROP TRIGGER item_no_update_delete ON oversight_batchitem;
DROP POLICY item_insert ON oversight_batchitem;
DROP POLICY item_read ON oversight_batchitem;
ALTER TABLE oversight_batchitem DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON oversight_batchitem TO gj_app;
DROP TRIGGER batch_no_truncate ON oversight_oversightbatch;
DROP TRIGGER batch_no_update_delete ON oversight_oversightbatch;
DROP POLICY batch_insert ON oversight_oversightbatch;
DROP POLICY batch_read ON oversight_oversightbatch;
ALTER TABLE oversight_oversightbatch DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON oversight_oversightbatch TO gj_app;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("oversight", "0001_initial"),
        ("positions", "0002_one_position_per_area"),
        ("identity", "0009_otp_purpose_decision"),
        ("core", "0002_append_only_guard"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass. `decided_at__date` uses the current time zone, Asia/Kolkata, and `set_decided_on` uses local noon, so dates match.

- [ ] **Step 5: Update CODEMAP and commit**

`docs/CODEMAP.md` changes:
- New `### oversight` section: models, service, command and migration.
- Roles table:
  - Superintendent: sees the batches of the district position they hold.
  - Head Authority and Software Owner: read all batches.
  - Licensing Authority: sets review periods through the service; the screen comes in D3.
- Conventions:
  - "Periods run back to back from `starts_on`; a batch is created only after its period ends; sign-off is due 30 days later."
  - "The review setting has no row-level security (configuration, ruling D-R6 style)."
- Add the new tests and update the count.

```bash
uv run ruff format . && uv run ruff check . && uv run --env-file .env.test python manage.py makemigrations --check --dry-run
git add oversight/ config/ tests/conftest.py tests/test_oversight_batches.py ../docs/CODEMAP.md
git commit -m "feat: superintendent review periods and idempotent batch creation"
```

---

### Task 4: Flags and one-time-code-signed sign-off

**Files:**
- Modify: `backend/oversight/models.py`, `backend/oversight/service.py`, `docs/CODEMAP.md`
- Create (generated): `backend/oversight/migrations/0003_flags_and_sign_offs.py`. Generate it, then append the row-level-security and append-only SQL to it as a `RunSQL` operation.
- Test: `backend/tests/test_oversight_review.py`

**Interfaces:**
- Consumes:
  - `alerts.service.raise_flag_alert`
  - `reasons.service.resolve_reason`, `InvalidReason`
  - `ReasonKind.SUPERINTENDENT_FLAG`
  - `identity.otp.issue` and `verify`, `OtpPurpose.DECISION`
  - `positions.service.positions_held`
  - `transactions.models.TransactionDecision`, `DecisionStep`, `DecisionOutcome`
- Produces:
  - `BatchFlag(item one-to-one, reason, comment, flagged_by, position, created_at)`
  - `BatchSignOff(batch one-to-one, signed_by, position, otp_verified_at, created_at)`
  - `oversight.service.NotAllowed(Exception)`
  - `oversight.service.batch_status(batch, today) -> str`, returning `"SIGNED"`, `"OVERDUE"` or `"OPEN"`
  - `oversight.service.flag_item(*, batch_id: int, reference: str, user: User, reason_code: str, comment: str) -> BatchFlag`
  - `oversight.service.request_sign_off_code(*, batch_id: int, user: User) -> OtpChallenge`
  - `oversight.service.sign_off(*, batch_id: int, user: User, challenge_id: str, code: str) -> BatchSignOff | None`, which returns `None` on a wrong code

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_oversight_review.py`:
```python
from datetime import date

import pytest
from django.db import DatabaseError, transaction

from alerts.models import AuthorityAlert
from core.db_context import acting_as_system, set_actor
from identity.models import OtpChallenge
from oversight.models import BatchFlag, BatchSignOff
from oversight.service import (
    NotAllowed, batch_status, create_due_batches, flag_item, request_sign_off_code, sign_off,
)
from reasons.service import InvalidReason
from tests.conftest import set_decided_on

pytestmark = pytest.mark.django_db


@pytest.fixture
def batch(settle, review_setting):
    tx = settle()
    set_decided_on(tx, date(2026, 6, 10))
    with acting_as_system("test"):
        [made] = create_due_batches(date(2026, 6, 16))
    return made, tx


def as_user(user):
    set_actor(user_id=user.user_id, role=user.role)


def sign(user, batch_id, otp_outbox, code=None):
    as_user(user)
    challenge = request_sign_off_code(batch_id=batch_id, user=user)
    return sign_off(batch_id=batch_id, user=user, challenge_id=str(challenge.public_id), code=code or otp_outbox[-1][1])


def test_flag_alerts_the_approving_officer(app_db, org, trade, batch, audit_actions):
    made, tx = batch
    as_user(trade.superintendent)
    flag = flag_item(batch_id=made.id, reference=tx.reference, user=trade.superintendent,
                     reason_code="QUANTITY_UNUSUAL", comment="Twice the usual volume")
    assert flag.position == org.district_officer and flag.flagged_by == trade.superintendent.user_id
    with acting_as_system("test"):
        alert = AuthorityAlert.objects.get(kind="SUPERINTENDENT_FLAG")
    assert alert.position == org.area_officer and alert.transaction == tx
    assert alert.comment == "Twice the usual volume"
    assert audit_actions()[-1] == "oversight.transaction_flagged"


def test_flag_needs_a_flag_reason(app_db, trade, batch):
    made, tx = batch
    as_user(trade.superintendent)
    with pytest.raises(InvalidReason):
        flag_item(batch_id=made.id, reference=tx.reference, user=trade.superintendent,
                  reason_code="NOT_ORDERED", comment="")
    with pytest.raises(InvalidReason, match="describe the reason"):
        flag_item(batch_id=made.id, reference=tx.reference, user=trade.superintendent, reason_code="OTHER", comment=" ")


def test_one_flag_per_transaction(app_db, trade, batch):
    made, tx = batch
    as_user(trade.superintendent)
    flag_item(batch_id=made.id, reference=tx.reference, user=trade.superintendent, reason_code="PATTERN_CONCERN", comment="")
    with pytest.raises(NotAllowed, match="already flagged"):
        flag_item(batch_id=made.id, reference=tx.reference, user=trade.superintendent,
                  reason_code="PATTERN_CONCERN", comment="")


def test_only_the_superintendent_can_review(app_db, trade, batch):
    made, tx = batch
    as_user(trade.officer)
    with pytest.raises(NotAllowed, match="Only the superintendent"):
        flag_item(batch_id=made.id, reference=tx.reference, user=trade.officer, reason_code="PATTERN_CONCERN", comment="")
    with pytest.raises(NotAllowed):
        request_sign_off_code(batch_id=made.id, user=trade.officer)


def test_transaction_must_be_in_the_batch(app_db, trade, batch, settle):
    made, _ = batch
    other = settle()
    as_user(trade.superintendent)
    with pytest.raises(NotAllowed, match="not in this batch"):
        flag_item(batch_id=made.id, reference=other.reference, user=trade.superintendent,
                  reason_code="PATTERN_CONCERN", comment="")


def test_sign_off_with_code(app_db, trade, batch, otp_outbox, audit_actions):
    made, _ = batch
    signed = sign(trade.superintendent, made.id, otp_outbox)
    assert signed.signed_by == trade.superintendent.user_id and signed.otp_verified_at is not None
    assert batch_status(made, date(2026, 6, 30)) == "SIGNED"
    assert audit_actions()[-1] == "oversight.batch_signed"


def test_wrong_code_does_not_sign(app_db, trade, batch, otp_outbox):
    made, _ = batch
    as_user(trade.superintendent)
    challenge = request_sign_off_code(batch_id=made.id, user=trade.superintendent)
    real = otp_outbox[-1][1]
    wrong = "000000" if real != "000000" else "111111"
    assert sign_off(batch_id=made.id, user=trade.superintendent, challenge_id=str(challenge.public_id), code=wrong) is None
    assert OtpChallenge.objects.get(pk=challenge.pk).attempts == 1
    with acting_as_system("test"):
        assert BatchSignOff.objects.count() == 0


def test_signed_batch_cannot_be_flagged_or_signed_again(app_db, trade, batch, otp_outbox):
    made, tx = batch
    sign(trade.superintendent, made.id, otp_outbox)
    as_user(trade.superintendent)
    with pytest.raises(NotAllowed, match="already signed off"):
        flag_item(batch_id=made.id, reference=tx.reference, user=trade.superintendent,
                  reason_code="PATTERN_CONCERN", comment="")
    with pytest.raises(NotAllowed, match="already signed off"):
        request_sign_off_code(batch_id=made.id, user=trade.superintendent)


def test_batch_status_open_then_overdue(app_db, batch):
    made, _ = batch
    assert batch_status(made, date(2026, 7, 15)) == "OPEN"
    assert batch_status(made, date(2026, 7, 16)) == "OVERDUE"


def test_flags_and_sign_offs_are_append_only_even_for_owner(db, trade, batch, otp_outbox):
    made, tx = batch
    as_user(trade.superintendent)
    flag_item(batch_id=made.id, reference=tx.reference, user=trade.superintendent, reason_code="PATTERN_CONCERN", comment="")
    sign(trade.superintendent, made.id, otp_outbox)
    for model in (BatchFlag, BatchSignOff):
        with pytest.raises(DatabaseError, match="append-only"):
            with transaction.atomic():
                model.objects.update(created_at=None)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_oversight_review.py -v`
Expected: `ImportError` (`BatchFlag` and `flag_item` do not exist yet).

- [ ] **Step 3: Write the models and migration**

Append to `backend/oversight/models.py`, adding the import `from reasons.models import ReasonCode`:
```python
class BatchFlag(models.Model):
    item = models.OneToOneField(BatchItem, on_delete=models.PROTECT, related_name="flag")
    reason = models.ForeignKey(ReasonCode, on_delete=models.PROTECT)
    comment = models.TextField(blank=True)
    flagged_by = models.CharField(max_length=12)
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class BatchSignOff(models.Model):
    batch = models.OneToOneField(OversightBatch, on_delete=models.PROTECT, related_name="sign_off")
    signed_by = models.CharField(max_length=12)
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="+")
    otp_verified_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
```
Run `makemigrations oversight --name flags_and_sign_offs`. Then **append** to that generated migration's `operations`:
```python
        migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD),
```
Define `FORWARD` and `BACKWARD` at module level, using the same `ROLE` and `_append_only` helper as 0002, copied into this file. Migrations must stay self-contained.
- **Flags** (`oversight_batchflag`): read policy `item_id IN (SELECT id FROM oversight_batchitem)`, insert SYSTEM only, append-only with prefix `flag`.
- **Sign-offs** (`oversight_batchsignoff`): read policy `batch_id IN (SELECT id FROM oversight_oversightbatch)`, insert SYSTEM only, append-only with prefix `signoff`.

Add `("core", "0002_append_only_guard")` to its dependencies.

- [ ] **Step 4: Write the review services**

Append to `backend/oversight/service.py`, adding these imports:
```python
from django.db import connection

from alerts.service import raise_flag_alert
from core.db_context import acting_as_system
from identity import otp
from identity.models import OtpChallenge, OtpPurpose, User
from oversight.models import BatchFlag, BatchSignOff
from positions.service import positions_held
from reasons.models import ReasonKind
from reasons.service import resolve_reason
from transactions.models import DecisionOutcome, DecisionStep, TransactionDecision
```

```python
class NotAllowed(Exception):
    pass


ALREADY_SIGNED = "This batch is already signed off."


def batch_status(batch: OversightBatch, today: date) -> str:
    if BatchSignOff.objects.filter(batch=batch).exists():
        return "SIGNED"
    return "OVERDUE" if today > batch.due_on() else "OPEN"


def _own_open_batch(batch_id: int, user: User) -> OversightBatch:
    batch = OversightBatch.objects.select_related("position").filter(pk=batch_id).first()
    if batch is None or batch.position not in positions_held(user):
        raise NotAllowed("Only the superintendent holding this position can review this batch.")
    if BatchSignOff.objects.filter(batch=batch).exists():
        raise NotAllowed(ALREADY_SIGNED)
    return batch


def _lock_batch(batch: OversightBatch) -> None:
    """Batches are append-only (no row lock possible), so serialise flag/sign-off per batch."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"oversight-batch:{batch.id}"])


def flag_item(*, batch_id: int, reference: str, user: User, reason_code: str, comment: str) -> BatchFlag:
    batch = _own_open_batch(batch_id, user)
    item = batch.items.select_related("transaction").filter(transaction__reference=reference).first()
    if item is None:
        raise NotAllowed("That transaction is not in this batch.")
    reason = resolve_reason(ReasonKind.SUPERINTENDENT_FLAG, reason_code, comment)
    with acting_as_system("flag_transaction"):
        _lock_batch(batch)
        if BatchSignOff.objects.filter(batch=batch).exists():
            raise NotAllowed(ALREADY_SIGNED)
        if BatchFlag.objects.filter(item=item).exists():
            raise NotAllowed("This transaction is already flagged in this batch.")
        flag = BatchFlag.objects.create(item=item, reason=reason, comment=comment.strip(),
                                        flagged_by=user.user_id, position=batch.position)
        approving = TransactionDecision.objects.get(
            transaction=item.transaction, step=DecisionStep.OFFICER, outcome=DecisionOutcome.APPROVE
        )
        raise_flag_alert(tx=item.transaction, position=approving.position, reason=reason, comment=comment.strip())
        record(action="oversight.transaction_flagged", actor=user.user_id, subject_type="transaction",
               subject_id=item.transaction.reference, payload={"batch_id": batch.id})
    return flag


def request_sign_off_code(*, batch_id: int, user: User) -> OtpChallenge:
    _own_open_batch(batch_id, user)
    return otp.issue(user, OtpPurpose.DECISION)


def sign_off(*, batch_id: int, user: User, challenge_id: str, code: str) -> BatchSignOff | None:
    batch = _own_open_batch(batch_id, user)
    signer = otp.verify(challenge_id=challenge_id, purpose=OtpPurpose.DECISION, code=code)
    if signer is None:
        return None  # wrong or expired code: the attempt counts, nothing else changes
    if signer.pk != user.pk:
        raise NotAllowed("This code belongs to someone else.")
    with acting_as_system("sign_off_batch"):
        _lock_batch(batch)
        if BatchSignOff.objects.filter(batch=batch).exists():
            raise NotAllowed(ALREADY_SIGNED)
        signed = BatchSignOff.objects.create(batch=batch, signed_by=user.user_id, position=batch.position,
                                             otp_verified_at=timezone.now())
        record(action="oversight.batch_signed", actor=user.user_id, subject_type="batch", subject_id=str(batch.id))
    return signed
```
`_own_open_batch` reads under the caller's row-level-security context. The superintendent sees their own batches; anyone else gets `None`, then `NotAllowed`. Items and the approving decision are read inside the SYSTEM block, except `batch.items`, which follows the batch's visibility and works for the holder.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass. If `model.objects.update(created_at=None)` hits a NOT NULL error before the trigger runs, use a value instead: `update(comment="x")` for `BatchFlag` and `update(signed_by="x")` for `BatchSignOff`.

- [ ] **Step 6: Update CODEMAP and commit**

`docs/CODEMAP.md` changes:
- Superintendent role row: flags transactions in their batch (the flag alerts the approving officer's position), and signs off the batch with a one-time code.
- Section 4: the oversight lock order (user, then challenge, then batch advisory lock, then inserts, then audit).
- Add the new tests and update the count.

```bash
uv run ruff format . && uv run ruff check . && uv run --env-file .env.test python manage.py makemigrations --check --dry-run
git add oversight/ tests/test_oversight_review.py ../docs/CODEMAP.md
git commit -m "feat: superintendent flags (alerting the approving officer) and OTP-signed batch sign-off"
```

---

### Task 5: Oversight API

**Files:**
- Create: `backend/oversight/presenters.py`, `serializers.py`, `views.py`, `urls.py`
- Modify: `backend/config/urls.py`, `docs/CODEMAP.md`, `docs/superpowers/plans/2026-09-26-roadmap.md`
- Test: `backend/tests/test_oversight_api.py`

**Interfaces:**
- Consumes: Tasks 3 and 4, plus the alerts and transactions presenters' helpers.
- Produces:
  - `oversight.presenters.batch_summary(batch, today) -> dict`, with keys `id`, `position`, `period_start`, `period_end`, `due_on`, `status`, `item_count`, `flag_count`, `signed_at` and `signed_by`
  - `oversight.presenters.batch_detail(batch, today, viewer) -> dict`, which is the summary plus `items`
    - Each item has `reference`, `substance`, `quantity`, `unit`, `seller_name`, `buyer_name`, `approved_at`, `approved_by_position` and `flag`. `flag` is `{reason, comment, flagged_at}` or `None`.
  - `can_sign: bool`
  - HTTP API (any logged-in user; row-level security scopes the batches):
    - `GET /api/oversight/batches` returns 200 `[batch_summary]`, newest period first.
    - `GET /api/oversight/batches/<id>` returns 200 `batch_detail`, or 404.
    - `POST /api/oversight/batches/<id>/flag` with `{reference, reason_code, comment?}` returns 200 `batch_detail`, 400 `{detail}` or 403 `{detail}`.
    - `POST /api/oversight/batches/<id>/sign-off-code` returns 200 `{challenge_id}` or 403.
    - `POST /api/oversight/batches/<id>/sign-off` with `{challenge_id, code}` returns:
      - 200 with `batch_detail`
      - 401 `{"detail": "The code is wrong or has expired. Request a new code."}`
      - 403

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_oversight_api.py`:
```python
from datetime import date

import pytest

from core.db_context import acting_as_system
from oversight.service import create_due_batches
from tests.conftest import TEST_PASSWORD, set_decided_on

pytestmark = pytest.mark.django_db


def login(client, user, otp_outbox):
    client.logout()
    first = client.post("/api/auth/login", {"user_id": user.user_id, "password": TEST_PASSWORD},
                        content_type="application/json")
    client.post("/api/auth/login/verify", {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
                content_type="application/json")


def post(client, url, body=None):
    return client.post(url, body or {}, content_type="application/json")


@pytest.fixture
def batch_id(settle, review_setting):
    tx = settle()
    set_decided_on(tx, date(2026, 6, 10))
    with acting_as_system("test"):
        [made] = create_due_batches(date(2026, 6, 16))
    return made.id, tx.reference


def test_superintendent_reviews_flags_and_signs(app_db, client, trade, batch_id, otp_outbox):
    bid, ref = batch_id
    login(client, trade.superintendent, otp_outbox)
    [summary] = client.get("/api/oversight/batches").json()
    assert summary["item_count"] == 1 and summary["flag_count"] == 0
    assert summary["position"] == "District Officer, Ahmedabad"
    detail = client.get(f"/api/oversight/batches/{bid}").json()
    assert detail["can_sign"] is True
    assert detail["items"][0]["reference"] == ref
    assert detail["items"][0]["approved_by_position"] == "Area Officer, Sanand"
    flagged = post(client, f"/api/oversight/batches/{bid}/flag",
                   {"reference": ref, "reason_code": "QUANTITY_UNUSUAL", "comment": "Check volumes"}).json()
    assert flagged["flag_count"] == 1 and flagged["items"][0]["flag"]["reason"] == "Quantity unusually high"
    challenge = post(client, f"/api/oversight/batches/{bid}/sign-off-code").json()["challenge_id"]
    signed = post(client, f"/api/oversight/batches/{bid}/sign-off", {"challenge_id": challenge, "code": otp_outbox[-1][1]})
    assert signed.status_code == 200 and signed.json()["status"] == "SIGNED" and signed.json()["can_sign"] is False


def test_flag_reaches_the_officer_as_an_alert(app_db, client, trade, batch_id, otp_outbox):
    bid, ref = batch_id
    login(client, trade.superintendent, otp_outbox)
    post(client, f"/api/oversight/batches/{bid}/flag", {"reference": ref, "reason_code": "PATTERN_CONCERN"})
    login(client, trade.officer, otp_outbox)
    alerts = client.get("/api/alerts").json()["alerts"]
    assert [a["kind"] for a in alerts] == ["SUPERINTENDENT_FLAG"] and alerts[0]["pattern"] is None


def test_others_cannot_see_or_act_on_batches(app_db, client, trade, batch_id, otp_outbox):
    bid, ref = batch_id
    login(client, trade.officer, otp_outbox)
    assert client.get("/api/oversight/batches").json() == []
    assert client.get(f"/api/oversight/batches/{bid}").status_code == 404
    assert post(client, f"/api/oversight/batches/{bid}/flag",
                {"reference": ref, "reason_code": "PATTERN_CONCERN"}).status_code == 403


def test_bad_reason_is_400_and_wrong_code_is_401(app_db, client, trade, batch_id, otp_outbox):
    bid, ref = batch_id
    login(client, trade.superintendent, otp_outbox)
    assert post(client, f"/api/oversight/batches/{bid}/flag",
                {"reference": ref, "reason_code": "NOT_ORDERED"}).status_code == 400
    challenge = post(client, f"/api/oversight/batches/{bid}/sign-off-code").json()["challenge_id"]
    real = otp_outbox[-1][1]
    wrong = "000000" if real != "000000" else "111111"
    response = post(client, f"/api/oversight/batches/{bid}/sign-off", {"challenge_id": challenge, "code": wrong})
    assert response.status_code == 401
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_oversight_api.py -v`
Expected: 404 on `/api/oversight/...`.

- [ ] **Step 3: Write the presenters, serializers, views and URLs**

`backend/oversight/presenters.py`:
```python
"""What a superintendent (or Head Authority) sees of a batch. Party names are read as SYSTEM;
no licence numbers, GSTINs or contacts are included."""

from datetime import date

from core.db_context import acting_as_system
from identity.models import User
from oversight.models import BatchSignOff, OversightBatch
from oversight.service import batch_status
from positions.service import positions_held
from transactions.checks import fmt_qty
from transactions.models import DecisionOutcome, DecisionStep, TransactionDecision


def batch_summary(batch: OversightBatch, today: date) -> dict:
    signed = BatchSignOff.objects.filter(batch=batch).first()
    return {
        "id": batch.id, "position": batch.position.title,
        "period_start": batch.period_start.isoformat(), "period_end": batch.period_end.isoformat(),
        "due_on": batch.due_on().isoformat(), "status": batch_status(batch, today),
        "item_count": batch.items.count(), "flag_count": batch.items.filter(flag__isnull=False).count(),
        "signed_at": signed.created_at.isoformat() if signed else None,
        "signed_by": signed.signed_by if signed else None,
    }


def _item(item) -> dict:
    tx = item.transaction
    with acting_as_system("batch_view"):
        names = (tx.seller_licence.holder_name, tx.buyer_licence.holder_name)
        approval = TransactionDecision.objects.select_related("position").get(
            transaction=tx, step=DecisionStep.OFFICER, outcome=DecisionOutcome.APPROVE
        )
    flag = getattr(item, "flag", None)
    return {
        "reference": tx.reference, "substance": tx.substance.name, "quantity": fmt_qty(tx.quantity),
        "unit": tx.unit, "seller_name": names[0], "buyer_name": names[1],
        "approved_at": approval.created_at.isoformat(), "approved_by_position": approval.position.title,
        "flag": {"reason": flag.reason.label, "comment": flag.comment or None,
                 "flagged_at": flag.created_at.isoformat()} if flag else None,
    }


def batch_detail(batch: OversightBatch, today: date, viewer: User) -> dict:
    summary = batch_summary(batch, today)
    items = batch.items.select_related("transaction__substance").order_by("id")
    return {
        **summary,
        "items": [_item(item) for item in items],
        "can_sign": summary["status"] != "SIGNED" and batch.position in positions_held(viewer),
    }
```
The `transaction` foreign key on `BatchItem` points at a transaction the superintendent can read through `tx_officer_read`, because the superintendent position matches. Head Authority can read it too.

`backend/oversight/serializers.py`:
```python
"""Input validation for oversight endpoints."""

from rest_framework import serializers


class FlagSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=12)
    reason_code = serializers.CharField(max_length=40)
    comment = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)


class SignOffSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")
```

`backend/oversight/views.py`:
```python
"""Superintendent review endpoints. Thin: validate, call a service, present. A wrong code is
RETURNED as 401 (the attempt commits); refusals are returned as 403/400."""

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from oversight.models import OversightBatch
from oversight.presenters import batch_detail, batch_summary
from oversight.serializers import FlagSerializer, SignOffSerializer
from oversight.service import NotAllowed, flag_item, request_sign_off_code, sign_off
from reasons.service import InvalidReason

WRONG_CODE = {"detail": "The code is wrong or has expired. Request a new code."}


def _visible(batch_id: int) -> OversightBatch | None:
    return OversightBatch.objects.select_related("position").filter(pk=batch_id).first()


def _detail(batch_id: int, user) -> Response:
    return Response(batch_detail(_visible(batch_id), timezone.localdate(), user))


class BatchListView(APIView):
    def get(self, request):
        today = timezone.localdate()
        rows = OversightBatch.objects.select_related("position").order_by("-period_start", "-id")
        return Response([batch_summary(b, today) for b in rows])


class BatchDetailView(APIView):
    def get(self, request, batch_id):
        if _visible(batch_id) is None:
            return Response({"detail": "Batch not found."}, status=status.HTTP_404_NOT_FOUND)
        return _detail(batch_id, request.user)


class FlagView(APIView):
    def post(self, request, batch_id):
        data = FlagSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            flag_item(batch_id=batch_id, user=request.user, **data.validated_data)
        except NotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except InvalidReason as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _detail(batch_id, request.user)


class SignOffCodeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request, batch_id):
        try:
            challenge = request_sign_off_code(batch_id=batch_id, user=request.user)
        except NotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"challenge_id": str(challenge.public_id)})


class SignOffView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request, batch_id):
        data = SignOffSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            signed = sign_off(batch_id=batch_id, user=request.user,
                              challenge_id=str(data.validated_data["challenge_id"]), code=data.validated_data["code"])
        except NotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        if signed is None:
            return Response(WRONG_CODE, status=status.HTTP_401_UNAUTHORIZED)
        return _detail(batch_id, request.user)
```

`backend/oversight/urls.py`:
```python
from django.urls import path

from oversight import views

urlpatterns = [
    path("oversight/batches", views.BatchListView.as_view()),
    path("oversight/batches/<int:batch_id>", views.BatchDetailView.as_view()),
    path("oversight/batches/<int:batch_id>/flag", views.FlagView.as_view()),
    path("oversight/batches/<int:batch_id>/sign-off-code", views.SignOffCodeView.as_view()),
    path("oversight/batches/<int:batch_id>/sign-off", views.SignOffView.as_view()),
]
```
Add `path("api/", include("oversight.urls")),` to `config/urls.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: D2b acceptance, CODEMAP, roadmap and commit**

`docs/CODEMAP.md` changes:
- Add rows for the oversight presenters, serializers, views and urls, and add the routes to the `config/urls.py` row.
- Add the new tests and update the count.

In the roadmap, change the D2b row to "Built, PR into dev".

Run:
```bash
uv run ruff format --check . && uv run ruff check .
uv run --env-file .env.test python manage.py makemigrations --check --dry-run
uv run --env-file .env.test pytest -v
```
Expected: clean, `No changes detected`, all pass.

```bash
git add oversight/ config/ tests/test_oversight_api.py ../docs/
git commit -m "feat: oversight API — batch review, flags and OTP sign-off"
```

---

## Spec coverage (D2b)

| Spec item (Revision 3) | Task |
|---|---|
| D9 / §5a: a buyer rejection alerts the designated officer **and** superintendent positions, in-app, with reason, comment and the 30-day pattern signal | 1, 2 |
| Alerts follow the position (transfers); acknowledgement is recorded with who acknowledged and when, and is append-only | 1, 2 |
| D11: a review period of 15, 30 or 60 days per superintendent, set by the Licensing Authority (service now, screen in D3) | 3 |
| Batches list every transaction approved in the district during the period; created after the period ends; idempotent | 3 |
| Superintendent flags with a reason code and comment; the flag alerts the approving officer; nothing is reversed | 4, 5 |
| Batch signed off with a one-time code; overdue status; append-only records | 4, 5 |
| Visibility: holders of the addressed or batch position, plus Head Authority, Software Owner and SYSTEM | 1, 3, 4 |
| Screens (alert bell, batch review), scheduling and seed data | **D3 / D4** |
