"""API contracts for the web app (D3 Task 2).

Each case drives a real endpoint, as the right role, with the shared synthetic fixtures. Run with
UPDATE_CONTRACTS=1 to (re)write `frontend/src/test/contracts/<name>.json`; otherwise the response's
SHAPE (keys and JSON value types, recursively) must match the committed file. The frontend's MSW
handlers serve these files, so the mocks always match the real API. Adding an endpoint the web app
uses means adding a case here.
"""

import json
import os
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.test import override_settings
from django.utils import timezone

from config.checks import DEMO_SENDER
from core.db_context import acting_as_system
from demo.dataset import PERSONAS
from demo.models import DemoPersona
from identity.roles import Role
from oversight.service import create_due_batches, set_review_period
from tests.conftest import BUYER_GSTIN, login_body, set_decided_on
from tests.test_buyer_stock_limit import buyer_holds
from tests.test_governance_api import RULE, decide, draft
from tests.test_transaction_api import NEW_TX, login, post
from tests.test_transaction_decisions import act, new_tx

pytestmark = pytest.mark.django_db
CONTRACTS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "test" / "contracts"
UPDATE = os.environ.get("UPDATE_CONTRACTS") == "1"
CHECK = {"buyer_gstin": BUYER_GSTIN, "substance_code": "WHISKY", "quantity": "150"}


# --- shape comparison -------------------------------------------------------------------------


def shape(value):
    """The JSON type tree of `value`: a list's shape is its first element's."""
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    if value is None:
        return None
    if isinstance(value, bool):
        return "boolean"
    return "number" if isinstance(value, int | float) else "string"


def differences(expected, actual, path="$") -> list[str]:
    """Where `actual`'s shape departs from `expected`'s. An empty list matches any list."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        found = [f"{path}.{k}: missing" for k in expected.keys() - actual.keys()]
        found += [f"{path}.{k}: unexpected" for k in actual.keys() - expected.keys()]
        for key in expected.keys() & actual.keys():
            found += differences(expected[key], actual[key], f"{path}.{key}")
        return found
    if isinstance(expected, list) and isinstance(actual, list):
        return differences(expected[0], actual[0], f"{path}[0]") if expected and actual else []
    return [] if expected == actual else [f"{path}: expected {expected}, got {actual}"]


def test_shape_helpers():
    sample = {"a": [{"b": 1, "c": None}], "d": "x", "e": True, "f": []}
    assert differences(shape(sample), shape(sample)) == []
    changed = {"a": [{"b": "1", "c": None}], "e": True, "f": [1], "g": 2.5}
    assert sorted(differences(shape(sample), shape(changed))) == [
        "$.a[0].b: expected number, got string",
        "$.d: missing",
        "$.g: unexpected",
    ]
    assert differences(shape({"c": None}), shape({"c": "now set"})) == [
        "$.c: expected None, got string"
    ]


# --- the cases --------------------------------------------------------------------------------

CASES = {}


def contract(name, status=200):
    def register(build):
        CASES[name] = (build, status)
        return build

    return register


@pytest.fixture
def ctx(
    app_db, client, catalogue, org, trade, threshold, settle, make_user, make_licence, otp_outbox
):
    return SimpleNamespace(
        client=client,
        catalogue=catalogue,
        org=org,
        trade=trade,
        settle=settle,
        make_user=make_user,
        make_licence=make_licence,
        otp_outbox=otp_outbox,
    )


def as_(ctx, user):
    login(ctx.client, user, ctx.otp_outbox)
    return ctx.client


def authority(ctx, role):
    contacts = {
        Role.LICENSING_AUTHORITY: "+919800000601",
        Role.HEAD_AUTHORITY: "+919800000602",
        Role.SOFTWARE_OWNER: "+919800000605",
    }
    return ctx.make_user(role=role, contact=contacts[role])


def open_batch(ctx):
    """An OPEN batch for the district superintendent holding one approved sale (dates relative
    to today, so `next_due` is set)."""
    today = timezone.localdate()
    tx = ctx.settle()
    set_decided_on(tx, today - timedelta(days=10))
    with acting_as_system("test"):
        set_review_period(
            position=ctx.org.district_officer,
            days=15,
            by="test",
            starts_on=today - timedelta(days=20),
        )
        [batch] = create_due_batches(today)
    return batch, tx


def buyer_rejection_alert(ctx):
    ctx.settle(buyer="REJECT", reason_code="NOT_ORDERED")
    client = as_(ctx, ctx.trade.officer)
    return client.get("/api/alerts").json()["alerts"][0]["id"]


# Identity and home ---------------------------------------------------------------------------


@contract("login_start")
def _(ctx):
    body = login_body(ctx.trade.seller)
    return post(ctx.client, "/api/auth/login", body)


@contract("login_verify")
def _(ctx):
    body = login_body(ctx.trade.seller)
    challenge = post(ctx.client, "/api/auth/login", body).json()["challenge_id"]
    code = ctx.otp_outbox[-1][1]
    return post(ctx.client, "/api/auth/login/verify", {"challenge_id": challenge, "code": code})


# Demo mode (D4): the persona list and the SMS inbox, both anonymous ------------------------

DEMO = {"DEMO_MODE": True, "OTP_SENDER": DEMO_SENDER, "DEMO_PASSWORD": "demo-password-2026"}


@contract("demo_personas")
def _(ctx):
    for persona, user in zip(PERSONAS, (ctx.trade.seller, ctx.trade.buyer), strict=False):
        DemoPersona.objects.create(key=persona.key, user_id=user.user_id)
    with override_settings(**DEMO):
        return ctx.client.get("/api/demo/personas")


@contract("demo_inbox")
def _(ctx):
    body = login_body(ctx.trade.seller)
    with override_settings(**DEMO):
        post(ctx.client, "/api/auth/login", body)
        return ctx.client.get("/api/demo/inbox")


def _awaiting_officer(ctx, qty="10"):
    tx = new_tx(ctx.trade, ctx.catalogue, qty=qty)
    act(ctx.trade.buyer, Role.LICENSEE, tx, ctx.otp_outbox, "CONFIRM")
    return tx


def _home_setup(ctx, name):
    """Some work for each role, so the mock home screens show non-zero counts."""
    if name == "licensee":
        new_tx(ctx.trade, ctx.catalogue, qty="10")
    elif name == "personnel":
        ctx.settle(buyer="REJECT", reason_code="NOT_ORDERED")
        _awaiting_officer(ctx)
    elif name == "superintendent":
        open_batch(ctx)
        ctx.settle("250", officer="RECOMMEND")
    elif name == "head_authority":
        _drafted(ctx, authority(ctx, Role.LICENSING_AUTHORITY))


def _me_and_home(name, who):
    @contract(f"me_{name}")
    def _me(ctx):
        return as_(ctx, who(ctx)).get("/api/auth/me")

    @contract(f"home_{name}")
    def _home(ctx):
        user = who(ctx)
        _home_setup(ctx, name)
        return as_(ctx, user).get("/api/home")


_me_and_home("licensee", lambda ctx: ctx.trade.seller)
_me_and_home("personnel", lambda ctx: ctx.trade.officer)
_me_and_home("superintendent", lambda ctx: ctx.trade.superintendent)
_me_and_home("licensing_authority", lambda ctx: authority(ctx, Role.LICENSING_AUTHORITY))
_me_and_home("head_authority", lambda ctx: authority(ctx, Role.HEAD_AUTHORITY))
_me_and_home("software_owner", lambda ctx: authority(ctx, Role.SOFTWARE_OWNER))


# Transactions --------------------------------------------------------------------------------


@contract("transactions_list")
def _(ctx):
    ctx.settle()
    return as_(ctx, ctx.trade.seller).get("/api/transactions?side=sales")


@contract("transaction_created", status=201)
def _(ctx):
    return post(as_(ctx, ctx.trade.seller), "/api/transactions", NEW_TX)


@contract("transaction_detail_seller")
def _(ctx):
    tx = new_tx(ctx.trade, ctx.catalogue, qty="10")
    return as_(ctx, ctx.trade.seller).get(f"/api/transactions/{tx.reference}")


@contract("transaction_detail_buyer")
def _(ctx):
    tx = new_tx(ctx.trade, ctx.catalogue, qty="10")
    return as_(ctx, ctx.trade.buyer).get(f"/api/transactions/{tx.reference}")


@contract("transaction_detail_buyer_stock_limit")
def _(ctx):
    buyer_holds(ctx.trade, ctx.catalogue)  # a 10 L sale takes the buyer over their limit
    tx = new_tx(ctx.trade, ctx.catalogue, qty="10")
    response = as_(ctx, ctx.trade.buyer).get(f"/api/transactions/{tx.reference}")
    assert response.json()["allowed_outcomes"] == ["REJECT"]
    return response


@contract("transaction_detail_officer")
def _(ctx):
    tx = _awaiting_officer(ctx)
    response = as_(ctx, ctx.trade.officer).get(f"/api/transactions/{tx.reference}")
    assert response.json()["allowed_outcomes"] == ["APPROVE", "REJECT"]
    return response


@contract("transaction_detail_officer_two_step")
def _(ctx):
    tx = _awaiting_officer(ctx, qty="250")
    response = as_(ctx, ctx.trade.officer).get(f"/api/transactions/{tx.reference}")
    assert response.json()["allowed_outcomes"] == ["RECOMMEND", "REJECT"]
    return response


@contract("transaction_detail_superintendent_final")
def _(ctx):
    tx = ctx.settle("250", officer="RECOMMEND")
    response = as_(ctx, ctx.trade.superintendent).get(f"/api/transactions/{tx.reference}")
    assert response.json()["your_role"] == "superintendent" and response.json()["can_decide"]
    return response


@contract("transaction_detail_authority")
def _(ctx):
    tx = ctx.settle("250", officer="RECOMMEND", superintendent="APPROVE")
    head = authority(ctx, Role.HEAD_AUTHORITY)
    return as_(ctx, head).get(f"/api/transactions/{tx.reference}")


@contract("transaction_check_ok")
def _(ctx):
    return post(as_(ctx, ctx.trade.seller), "/api/transactions/check", CHECK)


@contract("transaction_check_refused")
def _(ctx):
    body = {**CHECK, "quantity": "600"}
    response = post(as_(ctx, ctx.trade.seller), "/api/transactions/check", body)
    assert response.json()["ok"] is False
    return response


@contract("buyer_lookup")
def _(ctx):
    client = as_(ctx, ctx.trade.seller)
    return post(client, "/api/transactions/buyer-lookup", {"gstin": BUYER_GSTIN})


@contract("decision_code")
def _(ctx):
    tx = new_tx(ctx.trade, ctx.catalogue, qty="10")
    return post(as_(ctx, ctx.trade.buyer), f"/api/transactions/{tx.reference}/decision-code")


# The licensee's own records and the catalogue ------------------------------------------------


@contract("licences_mine")
def _(ctx):
    return as_(ctx, ctx.trade.seller).get("/api/licences/mine")


@contract("stock_mine")
def _(ctx):
    return as_(ctx, ctx.trade.seller).get("/api/stock/mine")


for _kind in ("BUYER_REJECTION", "OFFICER_REJECTION", "SUPERINTENDENT_FLAG"):

    @contract(f"reason_codes_{_kind.lower()}")
    def _(ctx, kind=_kind):
        return as_(ctx, ctx.trade.seller).get(f"/api/reason-codes?kind={kind}")


for _name, _path in (
    ("catalogue_substances", "/api/catalogue/substances"),
    ("catalogue_classes", "/api/catalogue/classes"),
    ("catalogue_licence_types", "/api/catalogue/licence-types"),
    ("catalogue_approval_thresholds", "/api/catalogue/approval-thresholds"),
):

    @contract(_name)
    def _(ctx, path=_path):
        return as_(ctx, ctx.trade.seller).get(path)


# Alerts and oversight ------------------------------------------------------------------------


@contract("alerts")
def _(ctx):
    buyer_rejection_alert(ctx)
    return ctx.client.get("/api/alerts")


@contract("alert_acknowledged")
def _(ctx):
    alert_id = buyer_rejection_alert(ctx)
    note = {"note": "Spoke to the seller."}
    return post(ctx.client, f"/api/alerts/{alert_id}/acknowledge", note)


@contract("oversight_batches")
def _(ctx):
    open_batch(ctx)
    return as_(ctx, ctx.trade.superintendent).get("/api/oversight/batches")


@contract("oversight_batch_detail")
def _(ctx):
    batch, tx = open_batch(ctx)
    client = as_(ctx, ctx.trade.superintendent)
    flag = {"reference": tx.reference, "reason_code": "QUANTITY_UNUSUAL", "comment": "Check"}
    assert post(client, f"/api/oversight/batches/{batch.id}/flag", flag).status_code == 200
    return client.get(f"/api/oversight/batches/{batch.id}")


@contract("review_settings")
def _(ctx):
    open_batch(ctx)  # gives the district position a period and a last batch
    return as_(ctx, authority(ctx, Role.LICENSING_AUTHORITY)).get("/api/oversight/review-settings")


@contract("review_setting_saved")
def _(ctx):
    open_batch(ctx)
    client = as_(ctx, authority(ctx, Role.LICENSING_AUTHORITY))
    url = f"/api/oversight/review-settings/{ctx.org.district_officer.id}"
    return client.put(url, {"period_days": 30}, content_type="application/json")


# Rule changes and the licence register -------------------------------------------------------


def _drafted(ctx, drafter, **kwargs):
    response = draft(as_(ctx, drafter), **kwargs)
    assert response.status_code == 201, response.json()
    return response.json()["id"]


@contract("rule_changes")
def _(ctx):
    _drafted(ctx, authority(ctx, Role.LICENSING_AUTHORITY))
    return as_(ctx, authority(ctx, Role.HEAD_AUTHORITY)).get("/api/rule-changes")


@contract("rule_change_new_licence_type")
def _(ctx):
    proposal_id = _drafted(ctx, authority(ctx, Role.LICENSING_AUTHORITY))
    return ctx.client.get(f"/api/rule-changes/{proposal_id}")  # the drafter's view


@contract("rule_change_rule_version")
def _(ctx):
    proposal_id = _drafted(ctx, ctx.trade.superintendent, kind="RULE_VERSION", payload=dict(RULE))
    head = authority(ctx, Role.HEAD_AUTHORITY)
    response = as_(ctx, head).get(f"/api/rule-changes/{proposal_id}")
    assert response.json()["current"] is not None and response.json()["can_decide"]
    return response


@contract("rule_change_threshold")
def _(ctx):
    payload = {"class_code": "SPIRITS", "superintendent_above_qty": "500"}
    licensing = authority(ctx, Role.LICENSING_AUTHORITY)
    proposal_id = _drafted(ctx, licensing, kind="APPROVAL_THRESHOLD", payload=payload)
    head = authority(ctx, Role.HEAD_AUTHORITY)
    response = as_(ctx, head).get(f"/api/rule-changes/{proposal_id}")
    assert response.json()["current"] is not None
    return response


@contract("rule_change_decided")
def _(ctx):
    proposal_id = _drafted(ctx, authority(ctx, Role.LICENSING_AUTHORITY))
    as_(ctx, authority(ctx, Role.HEAD_AUTHORITY))
    return decide(ctx.client, proposal_id, ctx.otp_outbox, note="Agreed with the district.")


@contract("licences_register")
def _(ctx):
    return as_(ctx, authority(ctx, Role.LICENSING_AUTHORITY)).get("/api/licences")


@contract("licence_search")
def _(ctx):
    client = as_(ctx, authority(ctx, Role.LICENSING_AUTHORITY))
    number = ctx.trade.seller_licence.number()
    return post(client, "/api/licences/search", {"number": number, "page": 1})


@contract("licence_detail")
def _(ctx):
    client = as_(ctx, authority(ctx, Role.LICENSING_AUTHORITY))
    return client.get(f"/api/licences/{ctx.trade.seller_licence.id}")


# Error bodies --------------------------------------------------------------------------------


@contract("error_400_field_errors", status=400)
def _(ctx):
    body = {**NEW_TX, "vehicle_number": "not a plate"}
    return post(as_(ctx, ctx.trade.seller), "/api/transactions", body)


@contract("error_400_unknown_filter", status=400)
def _(ctx):
    return as_(ctx, ctx.trade.seller).get("/api/transactions?side=both")


@contract("error_401_wrong_code", status=401)
def _(ctx):
    tx = new_tx(ctx.trade, ctx.catalogue, qty="10")
    client = as_(ctx, ctx.trade.buyer)
    challenge = post(client, f"/api/transactions/{tx.reference}/decision-code").json()
    wrong = "000000" if ctx.otp_outbox[-1][1] != "000000" else "111111"
    body = {**challenge, "code": wrong, "outcome": "CONFIRM"}
    return post(client, f"/api/transactions/{tx.reference}/decide", body)


@contract("error_403_not_signed_in", status=403)
def _(ctx):
    return ctx.client.get("/api/auth/me")


@contract("error_403_not_allowed", status=403)
def _(ctx):
    tx = new_tx(ctx.trade, ctx.catalogue, qty="10")
    return post(as_(ctx, ctx.trade.seller), f"/api/transactions/{tx.reference}/decision-code")


@contract("error_404_not_found", status=404)
def _(ctx):
    return as_(ctx, ctx.trade.seller).get("/api/transactions/TX-NONE")


@contract("error_409_conflict", status=409)
def _(ctx):
    alert_id = buyer_rejection_alert(ctx)
    post(ctx.client, f"/api/alerts/{alert_id}/acknowledge")
    return post(ctx.client, f"/api/alerts/{alert_id}/acknowledge")


@contract("error_422_review_setting", status=422)
def _(ctx):
    open_batch(ctx)  # with a batch, the new period must start the day after it
    client = as_(ctx, authority(ctx, Role.LICENSING_AUTHORITY))
    url = f"/api/oversight/review-settings/{ctx.org.district_officer.id}"
    body = {"period_days": 30, "starts_on": "2020-01-01"}
    return client.put(url, body, content_type="application/json")


@contract("error_422_transaction_refused", status=422)
def _(ctx):
    body = {**NEW_TX, "quantity": "600"}
    return post(as_(ctx, ctx.trade.seller), "/api/transactions", body)


# --- the test ---------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(CASES))
def test_contract(ctx, name):
    build, status = CASES[name]
    response = build(ctx)
    assert response.status_code == status, response.content
    body = response.json()
    path = CONTRACTS / f"{name}.json"
    if UPDATE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        return
    assert path.exists(), f"{path.name} is missing: run with UPDATE_CONTRACTS=1 and commit it"
    sample = json.loads(path.read_text())
    assert differences(shape(sample), shape(body)) == [], f"{name} no longer matches its contract"


def test_every_contract_file_has_a_case():
    """A stale contract file (its case renamed or removed) would keep serving outdated mocks."""
    if CONTRACTS.exists():
        assert {p.stem for p in CONTRACTS.glob("*.json")} <= set(CASES)
