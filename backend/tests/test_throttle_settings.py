"""Rate limits and the proxy count come from the environment, with safe defaults.

Each case loads `config.settings` in a fresh interpreter with a controlled environment, as the
process would start. The defaults are the production values; the demo stack raises some of them
(docker-compose.demo.yml, checked in test_compose_demo.py).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import override_settings
from rest_framework.throttling import ScopedRateThrottle

from config import env
from demo import views as demo_views

BACKEND = Path(__file__).resolve().parent.parent
OVERRIDABLE = (
    "DJANGO_NUM_PROXIES",
    "THROTTLE_RATE_LOGIN",
    "THROTTLE_RATE_OTP",
    "THROTTLE_RATE_ENROLMENT",
    "THROTTLE_RATE_LOOKUP",
    "THROTTLE_RATE_DEMO",
)
PRINT = (
    "import json, config.settings as s; "
    "print(json.dumps({'proxies': s.REST_FRAMEWORK['NUM_PROXIES'], "
    "'rates': s.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']}))"
)


def _load(**overrides: str) -> subprocess.CompletedProcess:
    environment = {k: v for k, v in os.environ.items() if k not in OVERRIDABLE}
    environment.update(overrides)
    return subprocess.run(  # noqa: S603 - fixed interpreter and code, test-controlled env
        [sys.executable, "-c", PRINT],
        cwd=BACKEND,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _settings(**overrides: str) -> dict:
    result = _load(**overrides)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_defaults_trust_no_proxy_and_keep_the_production_rates():
    loaded = _settings()
    assert loaded["proxies"] == 0
    assert loaded["rates"] == {
        "login": "10/min",
        "otp": "10/min",
        "enrolment": "10/min",
        "lookup": "30/min",
        "demo": "120/min",
    }


def test_every_rate_and_the_proxy_count_can_be_set():
    loaded = _settings(
        DJANGO_NUM_PROXIES="1",
        THROTTLE_RATE_LOGIN="60/min",
        THROTTLE_RATE_OTP="61/min",
        THROTTLE_RATE_ENROLMENT="5/hour",
        THROTTLE_RATE_LOOKUP="100/min",
        THROTTLE_RATE_DEMO="300/min",
    )
    assert loaded["proxies"] == 1
    assert loaded["rates"] == {
        "login": "60/min",
        "otp": "61/min",
        "enrolment": "5/hour",
        "lookup": "100/min",
        "demo": "300/min",
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"DJANGO_NUM_PROXIES": "-1"},
        {"DJANGO_NUM_PROXIES": "one"},
        {"THROTTLE_RATE_LOGIN": "lots"},
        {"THROTTLE_RATE_OTP": "10/fortnight"},
        {"THROTTLE_RATE_DEMO": "/min"},
    ],
)
def test_settings_refuse_to_load_a_bad_value(overrides):
    result = _load(**overrides)
    assert result.returncode != 0
    assert next(iter(overrides)) in result.stderr


# --- the helpers -------------------------------------------------------------------------


def test_count_defaults_and_parses(monkeypatch):
    monkeypatch.delenv("GJ_COUNT", raising=False)
    assert env.count("GJ_COUNT", 0) == 0
    monkeypatch.setenv("GJ_COUNT", " 2 ")
    assert env.count("GJ_COUNT", 0) == 2


@pytest.mark.parametrize("value", ["-1", "1.5", "two"])
def test_count_refuses_anything_but_a_whole_number(monkeypatch, value):
    monkeypatch.setenv("GJ_COUNT", value)
    with pytest.raises(env.MissingSetting, match="GJ_COUNT"):
        env.count("GJ_COUNT", 0)


@pytest.mark.parametrize("value", ["10/min", "1/s", "5/hour", "100/day", "3/m"])
def test_rate_accepts_what_drf_understands(monkeypatch, value):
    monkeypatch.setenv("GJ_RATE", value)
    assert env.rate("GJ_RATE", "1/min") == value
    ScopedRateThrottle().parse_rate(value)  # and DRF agrees


def test_rate_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("GJ_RATE", raising=False)
    assert env.rate("GJ_RATE", "30/min") == "30/min"


# --- the demo endpoints have a scope of their own --------------------------------------------


@pytest.mark.parametrize("view", [demo_views.InboxView, demo_views.PersonasView])
def test_demo_views_use_the_demo_scope(view):
    assert view.throttle_scope == "demo"
    assert view.throttle_classes == [ScopedRateThrottle]


@pytest.mark.django_db
def test_inbox_polling_does_not_use_the_lookup_budget(app_db, client, settings):
    rates = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "lookup": "1/min"}
    demo = {"DEMO_MODE": True, "OTP_SENDER": "demo.sender.DemoInboxOtpSender"}
    with override_settings(
        **demo, REST_FRAMEWORK={**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": rates}
    ):
        ScopedRateThrottle.THROTTLE_RATES = rates
        try:
            statuses = [client.get("/api/demo/inbox").status_code for _ in range(3)]
        finally:
            ScopedRateThrottle.THROTTLE_RATES = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert statuses == [200, 200, 200]
