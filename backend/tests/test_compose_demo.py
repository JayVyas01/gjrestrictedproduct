"""The offline demo stack (docker-compose.demo.yml) keeps to the demo fences.

Parsed as YAML, without Docker: only the web server publishes a port, and only on 127.0.0.1;
the database and backend stay on the stack's private network; demo mode runs with the values
the startup guard (config/checks.py) accepts.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from config.checks import DEMO_SENDER, demo_mode_problems

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
COMPOSE = yaml.safe_load((REPO / "docker-compose.demo.yml").read_text())
SERVICES = COMPOSE["services"]
BACKEND_ENV = SERVICES["backend"]["environment"]


def test_the_stack_has_the_three_services():
    assert set(SERVICES) == {"db", "backend", "web"}


def test_only_web_publishes_a_port_and_only_on_localhost():
    published = {name: svc.get("ports") for name, svc in SERVICES.items() if svc.get("ports")}
    assert published == {"web": ["127.0.0.1:8080:8080"]}


@pytest.mark.parametrize("name", ["db", "backend"])
def test_db_and_backend_are_not_reachable_from_the_host(name):
    assert "ports" not in SERVICES[name]
    assert SERVICES[name].get("network_mode") is None


def test_backend_runs_in_demo_mode_with_the_inbox_sender():
    assert BACKEND_ENV["DEMO_MODE"] == "1"
    assert BACKEND_ENV["OTP_SENDER"] == DEMO_SENDER
    assert BACKEND_ENV["DJANGO_DEBUG"] == "0"
    assert BACKEND_ENV["DJANGO_SSL_REDIRECT"] == "0"


def test_backend_runs_as_the_app_role_and_migrates_as_the_owner():
    assert BACKEND_ENV["DB_USER"] == "gj_app"
    assert BACKEND_ENV["DB_OWNER_USER"] == "gj_owner"
    assert BACKEND_ENV["DB_HOST"] == "db"


def test_the_superuser_password_reaches_only_the_database():
    for name in ("backend", "web"):
        values = " ".join(str(v) for v in (SERVICES[name].get("environment") or {}).values())
        assert "POSTGRES_SUPERUSER_PASSWORD" not in values
        assert "env_file" not in SERVICES[name]


def test_the_compose_values_pass_the_demo_mode_guard():
    from types import SimpleNamespace

    settings = SimpleNamespace(
        DEMO_MODE=BACKEND_ENV["DEMO_MODE"] == "1",
        ALLOWED_HOSTS=BACKEND_ENV["DJANGO_ALLOWED_HOSTS"].split(","),
        SECURE_SSL_REDIRECT=BACKEND_ENV["DJANGO_SSL_REDIRECT"] == "1",
        OTP_SENDER=BACKEND_ENV["OTP_SENDER"],
    )
    assert demo_mode_problems(settings) == []


def test_settings_load_with_the_compose_values():
    """The import-time guard in settings accepts the compose environment as a whole."""
    fixed = {k: v for k, v in BACKEND_ENV.items() if "${" not in str(v)}
    result = subprocess.run(  # noqa: S603 - fixed interpreter and code, test-controlled env
        [sys.executable, "-c", "import config.settings"],
        cwd=BACKEND,
        env={**os.environ, **fixed},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_services_start_in_dependency_order_once_healthy():
    assert SERVICES["backend"]["depends_on"] == {"db": {"condition": "service_healthy"}}
    assert SERVICES["web"]["depends_on"] == {"backend": {"condition": "service_healthy"}}
    for svc in SERVICES.values():
        assert "healthcheck" in svc


def test_the_database_lives_in_a_named_volume():
    volumes = SERVICES["db"]["volumes"]
    assert any(v.startswith("demo_pgdata:") for v in volumes)
    assert "demo_pgdata" in COMPOSE["volumes"]
