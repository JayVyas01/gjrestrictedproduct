"""seed_demo: a scripted, back-dated demo history built through the real services.

Seeding takes a few seconds and `app_db` is per test, so one test seeds and checks the whole
story in clearly separated blocks; the refusals are small tests of their own.
"""

from collections import Counter
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.utils import timezone

from alerts.models import AlertKind, AuthorityAlert
from audit.verify import verify_chain
from config.checks import DEMO_SENDER
from core.db_context import acting_as_system, set_actor
from core.home import home_counts
from demo import clock, dataset
from demo.models import DemoCredential, DemoInboxMessage, DemoPersona
from governance import service as governance
from governance.models import ProposalStatus, RuleChangeProposal
from identity.models import User
from licensing.models import Licence, LicenceStatus
from oversight.models import BatchFlag, OversightBatch
from oversight.service import batch_status
from transactions import service as transactions
from transactions.models import Transaction

DEMO_PASSWORD = "demo-password-2026"
DEMO = {"DEMO_MODE": True, "OTP_SENDER": DEMO_SENDER, "DEMO_PASSWORD": DEMO_PASSWORD}


def latest_code(user: User) -> str:
    return DemoInboxMessage.objects.filter(user_id=user.user_id).latest("id").code


def persona(key: str) -> User:
    return User.objects.get(user_id=DemoPersona.objects.get(key=key).user_id)


def act_as(user: User) -> None:
    set_actor(user_id=user.user_id, role=user.role)


def expected_status(sale: dataset.Sale) -> str:
    """The status a scripted sale ends in, read from its steps."""
    if sale.cancelled:
        return "CANCELLED"
    if sale.buyer is None:
        return "AWAITING_BUYER"
    if sale.buyer.outcome == "REJECT":
        return "REJECTED_BY_BUYER"
    if sale.officer is None:
        return "AWAITING_OFFICER"
    if sale.officer.outcome == "REJECT":
        return "REJECTED_BY_OFFICER"
    if sale.officer.outcome == "APPROVE":
        return "APPROVED"
    if sale.superintendent is None:
        return "AWAITING_SUPERINTENDENT"
    if sale.superintendent.outcome == "REJECT":
        return "REJECTED_BY_SUPERINTENDENT"
    return "APPROVED"


# --- The clock -------------------------------------------------------------------------------


def test_clock_moves_now_and_today_back_and_refuses_the_future():
    moment = clock.days_ago(10, "09:30")
    assert timezone.localtime(moment).hour == 9
    assert moment.tzinfo is not None
    with clock.at(moment):
        assert timezone.now() == moment
        assert timezone.localdate() == timezone.localdate(moment)
    assert timezone.now() - moment > timedelta(days=9)
    with pytest.raises(ValueError), clock.at(timezone.now() + timedelta(hours=1)):
        pass


# --- Refusals --------------------------------------------------------------------------------


def test_refuses_outside_demo_mode(app_db):
    with override_settings(DEMO_MODE=False), pytest.raises(CommandError, match="demo mode"):
        call_command("seed_demo")
    assert User.objects.count() == 0


def test_refuses_without_the_demo_password(app_db):
    with override_settings(**{**DEMO, "DEMO_PASSWORD": ""}):
        with pytest.raises(CommandError, match="DEMO_PASSWORD"):
            call_command("seed_demo")
    assert User.objects.count() == 0


def test_refuses_another_otp_sender(app_db):
    with override_settings(**{**DEMO, "OTP_SENDER": "identity.otp_delivery.OutboxOtpSender"}):
        with pytest.raises(CommandError, match="inbox"):
            call_command("seed_demo")


def test_refuses_a_database_that_already_has_licences(app_db, make_licence):
    make_licence()
    with override_settings(**DEMO), pytest.raises(CommandError, match="already has licences"):
        call_command("seed_demo")
    assert not DemoPersona.objects.exists()


# --- The whole story -------------------------------------------------------------------------


def test_seed_builds_the_scripted_story_through_the_real_services(app_db, client, capsys):
    with override_settings(**DEMO):
        call_command("seed_demo")
        output = capsys.readouterr().out
        assert "Audit chain OK" in output
        today = timezone.localdate()

        # Counts match the dataset.
        with acting_as_system("test"):
            assert Licence.objects.count() == sum(len(b.licences) for b in dataset.BUSINESSES)
            statuses = Counter(Transaction.objects.values_list("status", flat=True))
            assert statuses == Counter(expected_status(sale) for sale in dataset.SALES)
            assert RuleChangeProposal.objects.count() == len(dataset.PROPOSALS)
            assert sorted(RuleChangeProposal.objects.values_list("status", flat=True)) == [
                ProposalStatus.APPROVED,
                ProposalStatus.SUBMITTED,
                ProposalStatus.WITHDRAWN,
            ]
            suspended = Licence.objects.filter(status=LicenceStatus.SUSPENDED).count()
            assert suspended == len(dataset.STATUS_CHANGES)
            # The batches follow from the review periods (one per completed period).
            assert OversightBatch.objects.filter(position__code="DO-AHD").count() == 5
            assert OversightBatch.objects.filter(position__code="DO-VAD").count() == 2
            # Every transaction was started on a past day and its decisions came later.
            assert Transaction.objects.filter(created_at__gt=timezone.now()).count() == 0
            assert Transaction.objects.order_by("created_at").first().created_at.date() < (
                today - timedelta(days=60)
            )
        enrolled = [b for b in dataset.BUSINESSES if b.enrolled]
        assert User.objects.filter(role="LICENSEE").count() == len(enrolled)
        assert User.objects.count() == len(enrolled) + len(dataset.OFFICIALS)
        assert DemoPersona.objects.count() == len(dataset.PERSONAS)
        # Every account's password is recorded for the persona picker and the CSV (A7).
        credentials = {c.user_id: c.password() for c in DemoCredential.objects.all()}
        assert credentials == {
            user_id: DEMO_PASSWORD for user_id in User.objects.values_list("user_id", flat=True)
        }

        # The audit chain verifies.
        with acting_as_system("test"):
            report = verify_chain()
        assert report.ok, report.problem
        assert report.checked > 100

        # Something is waiting for each persona today (home counts through the real home_counts).
        for key in ("buyer", "area_officer", "superintendent"):
            user = persona(key)
            act_as(user)
            assert home_counts(user, today)["awaiting_your_decision"] >= 1, key
        seller = persona("seller")
        act_as(seller)
        assert home_counts(seller, today)["sales_in_progress"] >= 1
        officer = persona("area_officer")
        act_as(officer)
        assert home_counts(officer, today)["unacknowledged_alerts"] >= 1
        authority = persona("licensing_authority")
        act_as(authority)
        assert home_counts(authority, today)["expiring_licences_30d"] >= 1
        head_a = persona("head_authority_a")
        act_as(head_a)
        assert home_counts(head_a, today)["rule_changes_awaiting_you"] == 1

        # The Ahmedabad superintendent has an open batch (due soon); Vadodara an overdue one.
        superintendent = persona("superintendent")
        act_as(superintendent)
        counts = home_counts(superintendent, today)
        assert counts["open_batches"] >= 1 and counts["overdue_batches"] == 0
        assert counts["next_due"] <= (today + timedelta(days=15)).isoformat()
        with acting_as_system("test"):
            vadodara = OversightBatch.objects.filter(position__code="DO-VAD")
            assert "OVERDUE" in {batch_status(batch, today) for batch in vadodara}
            ahmedabad = OversightBatch.objects.filter(position__code="DO-AHD")
            signed = [b for b in ahmedabad if batch_status(b, today) == "SIGNED"]
            assert len(signed) == 3
            assert BatchFlag.objects.filter(item__batch__in=signed).count() == 1

        # The buyer's waiting purchases: one over the whisky stock limit, the others normal.
        buyer = persona("buyer")
        act_as(buyer)
        waiting = list(transactions.awaiting_decision_for(buyer).select_related("substance"))
        problems = {tx.substance.code: transactions.stock_limit_problem(tx) for tx in waiting}
        assert problems["WHISKY"] is not None
        assert problems["RUM"] is None and problems["VODKA"] is None

        # The next "I did not place this order" by the buyer is the seller's 3rd in 30 days.
        vodka = next(tx for tx in waiting if tx.substance.code == "VODKA")
        challenge = transactions.request_decision_code(reference=vodka.reference, user=buyer)
        rejected = transactions.decide(
            reference=vodka.reference,
            user=buyer,
            challenge_id=str(challenge.public_id),
            code=latest_code(buyer),
            outcome="REJECT",
            reason_code="NOT_ORDERED",
        )
        assert rejected.status == "REJECTED_BY_BUYER"
        with acting_as_system("test"):
            alerts = AuthorityAlert.objects.filter(
                transaction=rejected, kind=AlertKind.BUYER_REJECTION
            )
            assert {alert.pattern_count for alert in alerts} == {3}

        # Head A can decide the pending rule change; Head B (who drafted it) cannot.
        head_b = persona("head_authority_b")
        act_as(head_b)
        pending = RuleChangeProposal.objects.get(status=ProposalStatus.SUBMITTED)
        with pytest.raises(governance.OwnChange):
            governance.request_decision_code(proposal_id=pending.id, user=head_b)
        act_as(head_a)
        challenge = governance.request_decision_code(proposal_id=pending.id, user=head_a)
        decided = governance.decide(
            proposal_id=pending.id,
            user=head_a,
            challenge_id=str(challenge.public_id),
            code=latest_code(head_a),
            outcome="APPROVE",
        )
        assert decided.status == ProposalStatus.APPROVED

        # Every persona signs in through the real login API with the demo password and a code.
        set_actor(user_id="", role="")
        for entry in client.get("/api/demo/personas").json():
            assert entry["password"] == DEMO_PASSWORD
            started = client.post(
                "/api/auth/login",
                {
                    "role": entry["role"],
                    "identifier": entry["identifier"],
                    "password": entry["password"],
                },
                content_type="application/json",
            )
            assert started.status_code == 200, entry["key"]
            code = client.get("/api/demo/inbox").json()[0]["code"]
            verified = client.post(
                "/api/auth/login/verify",
                {"challenge_id": started.json()["challenge_id"], "code": code},
                content_type="application/json",
            )
            assert verified.status_code == 200, entry["key"]
            # Officials' passwords were issued, so they must change them first (A3).
            assert verified.json()["must_change_password"] is (entry["role"] != "PARTY")
            client.post("/api/auth/logout")


def test_the_dataset_keeps_to_the_synthetic_data_rules():
    from licensing.service import GSTIN_PATTERN

    for business in dataset.BUSINESSES:
        assert GSTIN_PATTERN.match(business.gstin) and business.gstin.startswith("99")
        assert business.contact.startswith("+91980000") and len(business.contact) == 13
        assert all(licence.number.startswith("DEMO/") for licence in business.licences)
    for official in dataset.OFFICIALS:
        assert official.contact.startswith("+91980000") and len(official.contact) == 13
    emails = [official.email for official in dataset.OFFICIALS]
    assert len(set(emails)) == len(emails)
    assert all(email.endswith("@demo.gujarat.example") for email in emails)
    contacts = [b.contact for b in dataset.BUSINESSES] + [o.contact for o in dataset.OFFICIALS]
    assert len(set(contacts)) == len(contacts)
    assert {Decimal(t.above_litres) for t in dataset.THRESHOLDS} == {Decimal("200")}
    assert len(dataset.SALES) >= 40
