# Demo D1 — Licensing Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tested backend for the licence-type catalogue, the area and position hierarchy, licence records with frozen permissions and validity periods, licence-gated enrolment, and a "my licences" API that feeds the permissions card.

**Architecture:** Three new Django apps, each exposing plain functions in `service.py`:
- `catalogue`: substances, licence types and versioned rules.
- `positions`: areas, positions and personnel assignments.
- `licensing`: licence records, `trading_permitted`, enrolment.

Licences are protected by Postgres row-level security: a licensee reads only licences whose GSTIN matches their account, and only the Licensing Authority or a SYSTEM job can write. Code that must look across owners, such as enrolment matching, runs inside `acting_as_system(job)`, which is explicit, short-lived and audited.

**Tech Stack:** Django 5.2, DRF 3.17, PostgreSQL 16, pytest-django. Same stack as Phase 1.

**Spec:** [`2026-09-28-licence-types-and-demo-design.md`](../specs/2026-09-28-licence-types-and-demo-design.md), sections 3, 4 and 5. **Builds on:** [`2026-09-26-phase1-foundation.md`](2026-09-26-phase1-foundation.md), which must be merged first. **Roadmap:** [`2026-09-26-roadmap.md`](2026-09-26-roadmap.md)

## Global Constraints

- Everything in the Phase 1 plan's Global Constraints applies unchanged: `app_db` in tests, never `transactional_db`; append-only tables revoke in a migration that depends on `("core", "0001_app_role_privileges")`; the pre-commit checks; and so on.
- **Licence application and renewal workflows are out of scope.** Licences and renewals are *recorded* by the Licensing Authority (spec D1, D5).
- The role is `Role.LICENSEE`; there are no buyer or seller roles (spec D4).
- A rule for the specific substance wins over a rule for its class. If there is no rule, the licence type is **not permitted** (spec section 4).
- Rule versions, validity periods and permission snapshots are append-only. Permissions are frozen on the licence when it is recorded and when each renewal is recorded (spec D3).
- `trading_permitted(licence, on)` is the only function that decides whether a licence allows trading. It is true only when the status is `ACTIVE` **and** a validity period covers `on` (spec section 5).
- Licence numbers, GSTINs and contacts are stored encrypted, with a blind index for exact-match lookup only. There is no partial search.
- An enrolment OTP goes **only** to the contact on the licence record, never to a contact supplied in the request.
- Quantities are `Decimal` values with 3 decimal places, in the substance's own unit (`L` or `KG`).
- Every user-facing failure message is plain language that says what to do (spec section 7).

## Review Focus

1. **A licence number typed in lowercase or with surrounding spaces** should still find the licence, while a partial number never should. Tested in Task 4.
2. **A substance with a class rule plus a stricter substance-specific rule** (for example selling not allowed) must follow the stricter substance rule. Tested in Task 2.
3. **An enrolment request that includes its own `contact` field** must still send the OTP to the contact on file. Tested in Task 5.
4. **An officer transferred off a position** must stop counting as its holder immediately, and the new holder must count at once. Tested in Task 3.
5. **A mistyped password during enrolment** must not use up the OTP, so the user can retry with the same code. Tested in Task 5.

## File Structure

```
backend/
  core/db_context.py                     # + acting_as_system()
  identity/models.py                     # OtpChallenge: user optional + subject; User: licensee_gstin_index
  identity/otp.py                        # + issue_for_subject(), verify_subject()
  catalogue/models.py, service.py        # substances, licence types, versioned rules, resolve_rule()
  catalogue/migrations/0002_append_only_versions.py
  positions/models.py, service.py        # areas, positions, assignments, covering_position(), assign()
  licensing/models.py                    # Licence, LicenceValidityPeriod, LicencePermissionsSnapshot
  licensing/service.py                   # record_licence, record_renewal, set_status, trading_permitted, ...
  licensing/enrolment.py                 # start_enrolment, complete_enrolment
  licensing/serializers.py, views.py, urls.py
  licensing/migrations/0002_rls_and_append_only.py
  tests/conftest.py                      # + catalogue, org, make_licence fixtures
  tests/test_otp_subject.py, test_catalogue.py, test_positions.py,
  tests/test_licensing.py, test_enrolment.py, test_licence_api.py
```

---

### Task 1: OTP for enrolment, before an account exists

**Files:**
- Modify: `backend/identity/models.py` (`OtpPurpose`, `OtpChallenge`)
- Modify: `backend/identity/otp.py` (full replacement below)
- Create (generated): `backend/identity/migrations/0004_otp_subject.py`
- Test: `backend/tests/test_otp_subject.py`

**Interfaces:**
- Consumes: Phase 1 `identity.otp.issue`, `identity.otp.verify`, `OtpChallenge`, `get_sender()`.
- Produces: `OtpPurpose.ENROL`; `OtpChallenge.subject: str` (max 100) and `OtpChallenge.user` now nullable, with exactly one of the two set; `identity.otp.issue_for_subject(*, subject: str, contact: str, purpose: str) -> OtpChallenge`; `identity.otp.verify_subject(*, challenge_id: str, purpose: str, code: str) -> str | None`. The behaviour of `issue` and `verify` is unchanged.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_otp_subject.py`:
```python
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from identity import otp
from identity.models import OtpChallenge, OtpPurpose

pytestmark = pytest.mark.django_db

SUBJECT = "gstin:" + "a" * 64


def test_subject_code_goes_to_the_given_contact(app_db, otp_outbox):
    otp.issue_for_subject(subject=SUBJECT, contact="+919800000555", purpose=OtpPurpose.ENROL)
    assert otp_outbox[-1][0] == "+919800000555"


def test_verify_subject_returns_subject_once(app_db, otp_outbox):
    challenge = otp.issue_for_subject(subject=SUBJECT, contact="+919800000555", purpose=OtpPurpose.ENROL)
    args = dict(challenge_id=str(challenge.public_id), purpose=OtpPurpose.ENROL, code=otp_outbox[-1][1])
    assert otp.verify_subject(**args) == SUBJECT
    assert otp.verify_subject(**args) is None


def test_user_verify_rejects_subject_challenge(app_db, otp_outbox):
    challenge = otp.issue_for_subject(subject=SUBJECT, contact="+919800000555", purpose=OtpPurpose.ENROL)
    code = otp_outbox[-1][1]
    assert otp.verify(challenge_id=str(challenge.public_id), purpose=OtpPurpose.ENROL, code=code) is None


def test_subject_verify_rejects_user_challenge(app_db, make_user, otp_outbox):
    challenge = otp.issue(make_user(), OtpPurpose.LOGIN)
    code = otp_outbox[-1][1]
    assert otp.verify_subject(challenge_id=str(challenge.public_id), purpose=OtpPurpose.LOGIN, code=code) is None


def test_new_subject_challenge_supersedes_old(app_db, otp_outbox):
    first = otp.issue_for_subject(subject=SUBJECT, contact="+919800000555", purpose=OtpPurpose.ENROL)
    first_code = otp_outbox[-1][1]
    otp.issue_for_subject(subject=SUBJECT, contact="+919800000555", purpose=OtpPurpose.ENROL)
    assert otp.verify_subject(challenge_id=str(first.public_id), purpose=OtpPurpose.ENROL, code=first_code) is None


def test_database_requires_exactly_one_of_user_or_subject(app_db, make_user):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OtpChallenge.objects.create(
                user=make_user(), subject=SUBJECT, purpose=OtpPurpose.ENROL,
                code_hash="x" * 64, expires_at=timezone.now(),
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_otp_subject.py -v`
Expected: FAIL with `AttributeError: ENROL` (or `issue_for_subject` not defined).

- [ ] **Step 3: Change the model**

In `backend/identity/models.py`, replace `OtpPurpose` and `OtpChallenge` with:
```python
class OtpPurpose(models.TextChoices):
    LOGIN = "LOGIN", "Login second factor"
    ENROL = "ENROL", "Licence-gated enrolment"


class OtpChallenge(models.Model):
    """One issued code, for an existing user OR for a subject that has no account yet
    (e.g. "gstin:<blind index>" during enrolment). Exactly one of the two is set."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="otp_challenges", null=True, blank=True
    )
    subject = models.CharField(max_length=100, blank=True)
    purpose = models.CharField(max_length=16, choices=OtpPurpose.choices)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, subject="")
                    | (models.Q(user__isnull=True) & ~models.Q(subject=""))
                ),
                name="otp_user_xor_subject",
            ),
        ]
```

Run: `uv run --env-file .env.test python manage.py makemigrations identity --name otp_subject`
Expected: creates `identity/migrations/0004_otp_subject.py`.

- [ ] **Step 4: Replace `backend/identity/otp.py`**

```python
"""Issue and check one-time passcodes.

Codes are stored only as an HMAC keyed with a server secret, so a database leak does not
reveal them. A challenge belongs either to a user (login, decisions) or to a subject that has
no account yet (enrolment). The caller must be inside a transaction.
"""

import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from identity.models import OtpChallenge, User
from identity.otp_delivery import get_sender

OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=5)
OTP_MAX_ATTEMPTS = 5


def _hash_code(challenge: OtpChallenge, code: str) -> str:
    message = f"{challenge.public_id}:{code}".encode()
    return hmac.new(settings.OTP_HMAC_KEY.encode(), message, hashlib.sha256).hexdigest()


def _new_code() -> str:
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def _create_and_send(challenge: OtpChallenge, contact: str) -> OtpChallenge:
    code = _new_code()
    challenge.code_hash = _hash_code(challenge, code)
    challenge.save()
    get_sender().send(contact, code)
    return challenge


def issue(user: User, purpose: str) -> OtpChallenge:
    now = timezone.now()
    OtpChallenge.objects.filter(user=user, purpose=purpose, closed_at__isnull=True).update(
        closed_at=now
    )
    challenge = OtpChallenge(user=user, purpose=purpose, expires_at=now + OTP_TTL)
    return _create_and_send(challenge, user.get_contact())


def issue_for_subject(*, subject: str, contact: str, purpose: str) -> OtpChallenge:
    now = timezone.now()
    OtpChallenge.objects.filter(subject=subject, purpose=purpose, closed_at__isnull=True).update(
        closed_at=now
    )
    challenge = OtpChallenge(subject=subject, purpose=purpose, expires_at=now + OTP_TTL)
    return _create_and_send(challenge, contact)


def _consume(
    *, challenge_id: str, purpose: str, code: str, usable: Callable[[OtpChallenge], bool]
) -> OtpChallenge | None:
    try:
        challenge = (
            OtpChallenge.objects.select_for_update()
            .select_related("user")
            .get(public_id=challenge_id, purpose=purpose, closed_at__isnull=True)
        )
    except (OtpChallenge.DoesNotExist, ValidationError):
        return None

    now = timezone.now()
    challenge.attempts += 1
    matches = hmac.compare_digest(challenge.code_hash, _hash_code(challenge, code))
    success = matches and now < challenge.expires_at and usable(challenge)
    if success or now >= challenge.expires_at or challenge.attempts >= OTP_MAX_ATTEMPTS:
        challenge.closed_at = now
    challenge.save(update_fields=["attempts", "closed_at"])
    return challenge if success else None


def verify(*, challenge_id: str, purpose: str, code: str) -> User | None:
    challenge = _consume(
        challenge_id=challenge_id,
        purpose=purpose,
        code=code,
        usable=lambda c: c.user is not None and c.user.is_active,
    )
    return challenge.user if challenge else None


def verify_subject(*, challenge_id: str, purpose: str, code: str) -> str | None:
    challenge = _consume(
        challenge_id=challenge_id, purpose=purpose, code=code, usable=lambda c: c.user is None
    )
    return challenge.subject if challenge else None
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass, including every Phase 1 OTP and login test.

- [ ] **Step 6: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add identity/ tests/test_otp_subject.py
git commit -m "feat: OTP challenges for subjects without an account (enrolment)"
```

---

### Task 2: Catalogue of substances, licence types and versioned rules

**Files:**
- Create: `backend/catalogue/__init__.py`, `apps.py`, `models.py`, `service.py`, `migrations/__init__.py`
- Create (generated): `backend/catalogue/migrations/0001_initial.py`
- Create: `backend/catalogue/migrations/0002_append_only_versions.py`
- Modify: `backend/config/settings.py` (`INSTALLED_APPS`), `backend/tests/conftest.py`
- Test: `backend/tests/test_catalogue.py`

**Interfaces:**
- Produces: models `Unit` (`LITRE="L"`, `KILOGRAM="KG"`), `SubstanceClass(code, name)`, `Substance(code, name, substance_class, unit)`, `LicenceType(code, name, description)`, `LicenceTypeRule(licence_type, substance | substance_class)`, `LicenceTypeRuleVersion(rule, version, may_buy, may_sell, may_transport, max_stock_qty, max_per_transaction_qty, validity_months, created_at, created_by)`; `catalogue.service.resolve_rule(licence_type, *, substance=None, substance_class=None) -> LicenceTypeRuleVersion | None`; `catalogue.service.add_rule_version(rule, *, created_by: str, may_buy: bool, may_sell: bool, may_transport: bool, max_stock_qty: Decimal, max_per_transaction_qty: Decimal, validity_months: int) -> LicenceTypeRuleVersion`; conftest fixture `catalogue` (a namespace with `spirits`, `whisky`, `rum`, `retail`, `wholesale`, `retail_rule`, `wholesale_rule`).

- [ ] **Step 1: Write the fixture and failing tests**

Add to `backend/tests/conftest.py` (imports at the top of the file):
```python
from decimal import Decimal
from types import SimpleNamespace

from catalogue.models import LicenceType, LicenceTypeRule, Substance, SubstanceClass, Unit
from catalogue.service import add_rule_version


def _permissions(**overrides):
    values = dict(
        may_buy=True, may_sell=True, may_transport=False,
        max_stock_qty=Decimal("1000"), max_per_transaction_qty=Decimal("500"), validity_months=12,
    )
    values.update(overrides)
    return values


@pytest.fixture
def catalogue(db):
    spirits = SubstanceClass.objects.create(code="SPIRITS", name="Spirits")
    whisky = Substance.objects.create(code="WHISKY", name="Whisky", substance_class=spirits, unit=Unit.LITRE)
    rum = Substance.objects.create(code="RUM", name="Rum", substance_class=spirits, unit=Unit.LITRE)
    retail = LicenceType.objects.create(code="RETAIL", name="Retail")
    wholesale = LicenceType.objects.create(code="WHOLESALE", name="Wholesale")
    retail_rule = LicenceTypeRule.objects.create(licence_type=retail, substance_class=spirits)
    add_rule_version(retail_rule, created_by="test", **_permissions())
    wholesale_rule = LicenceTypeRule.objects.create(licence_type=wholesale, substance_class=spirits)
    add_rule_version(
        wholesale_rule, created_by="test",
        **_permissions(may_transport=True, max_stock_qty=Decimal("50000"),
                       max_per_transaction_qty=Decimal("10000")),
    )
    return SimpleNamespace(
        spirits=spirits, whisky=whisky, rum=rum, retail=retail, wholesale=wholesale,
        retail_rule=retail_rule, wholesale_rule=wholesale_rule,
    )
```

`backend/tests/test_catalogue.py`:
```python
from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, transaction

from catalogue.models import LicenceType, LicenceTypeRule, LicenceTypeRuleVersion
from catalogue.service import add_rule_version, resolve_rule
from tests.conftest import _permissions

pytestmark = pytest.mark.django_db


def test_class_rule_applies_to_every_substance_in_the_class(app_db, catalogue):
    for substance in (catalogue.whisky, catalogue.rum):
        version = resolve_rule(catalogue.retail, substance=substance)
        assert version.rule == catalogue.retail_rule


def test_substance_rule_overrides_class_rule(app_db, catalogue):
    rum_only = LicenceTypeRule.objects.create(licence_type=catalogue.retail, substance=catalogue.rum)
    add_rule_version(rum_only, created_by="test", **_permissions(may_sell=False))
    version = resolve_rule(catalogue.retail, substance=catalogue.rum)
    assert version.rule == rum_only
    assert version.may_sell is False
    assert resolve_rule(catalogue.retail, substance=catalogue.whisky).may_sell is True


def test_no_rule_means_not_permitted(app_db, catalogue):
    manufacturer = LicenceType.objects.create(code="MANUFACTURER", name="Manufacturer")
    assert resolve_rule(manufacturer, substance=catalogue.whisky) is None


def test_class_scope_resolves_class_rule(app_db, catalogue):
    assert resolve_rule(catalogue.retail, substance_class=catalogue.spirits).rule == catalogue.retail_rule


def test_latest_version_wins_and_versions_increment(app_db, catalogue):
    newer = add_rule_version(
        catalogue.retail_rule, created_by="test", **_permissions(max_stock_qty=Decimal("2000"))
    )
    assert newer.version == 2
    assert resolve_rule(catalogue.retail, substance=catalogue.whisky) == newer


def test_rule_needs_exactly_one_scope(app_db, catalogue):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LicenceTypeRule.objects.create(
                licence_type=catalogue.retail, substance=catalogue.whisky, substance_class=catalogue.spirits
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LicenceTypeRule.objects.create(licence_type=catalogue.wholesale)


def test_rule_versions_cannot_be_edited(app_db, catalogue):
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic():
            LicenceTypeRuleVersion.objects.update(may_sell=False)


def test_limits_must_be_positive(app_db, catalogue):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            add_rule_version(catalogue.retail_rule, created_by="test", **_permissions(max_stock_qty=Decimal("0")))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_catalogue.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'catalogue'`.

- [ ] **Step 3: Write the app**

`backend/catalogue/__init__.py`, `backend/catalogue/migrations/__init__.py`: empty.

`backend/catalogue/apps.py`:
```python
from django.apps import AppConfig


class CatalogueConfig(AppConfig):
    name = "catalogue"
```

`backend/catalogue/models.py`:
```python
"""What can be traded, under which licence types, with which permissions.

Maintained by the Licensing Authority. Rule versions are never edited: a change is a new
version, and licences keep a frozen copy of the version they were recorded under.
"""

from django.db import models


class Unit(models.TextChoices):
    LITRE = "L", "Litres"
    KILOGRAM = "KG", "Kilograms"


class SubstanceClass(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.name


class Substance(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    substance_class = models.ForeignKey(SubstanceClass, on_delete=models.PROTECT, related_name="substances")
    unit = models.CharField(max_length=4, choices=Unit.choices)

    def __str__(self) -> str:
        return self.name


class LicenceType(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name


class LicenceTypeRule(models.Model):
    """Which licence type may deal in which substance or class. Scope is exactly one of the two."""

    licence_type = models.ForeignKey(LicenceType, on_delete=models.PROTECT, related_name="rules")
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT, null=True, blank=True)
    substance_class = models.ForeignKey(SubstanceClass, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(substance__isnull=False, substance_class__isnull=True)
                    | models.Q(substance__isnull=True, substance_class__isnull=False)
                ),
                name="rule_exactly_one_scope",
            ),
            models.UniqueConstraint(
                fields=["licence_type", "substance"],
                condition=models.Q(substance__isnull=False),
                name="one_rule_per_type_and_substance",
            ),
            models.UniqueConstraint(
                fields=["licence_type", "substance_class"],
                condition=models.Q(substance_class__isnull=False),
                name="one_rule_per_type_and_class",
            ),
        ]


class LicenceTypeRuleVersion(models.Model):
    rule = models.ForeignKey(LicenceTypeRule, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    may_buy = models.BooleanField()
    may_sell = models.BooleanField()
    may_transport = models.BooleanField()
    max_stock_qty = models.DecimalField(max_digits=12, decimal_places=3)
    max_per_transaction_qty = models.DecimalField(max_digits=12, decimal_places=3)
    validity_months = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rule", "version"], name="unique_rule_version"),
            models.CheckConstraint(
                condition=models.Q(max_stock_qty__gt=0, max_per_transaction_qty__gt=0),
                name="rule_limits_positive",
            ),
        ]
```

`backend/catalogue/service.py`:
```python
"""Look up the rule that governs a licence type for a substance or class."""

from decimal import Decimal

from catalogue.models import (
    LicenceType,
    LicenceTypeRule,
    LicenceTypeRuleVersion,
    Substance,
    SubstanceClass,
)


def _latest(rule: LicenceTypeRule | None) -> LicenceTypeRuleVersion | None:
    if rule is None:
        return None
    return rule.versions.order_by("-version").first()


def resolve_rule(
    licence_type: LicenceType,
    *,
    substance: Substance | None = None,
    substance_class: SubstanceClass | None = None,
) -> LicenceTypeRuleVersion | None:
    """Specific substance beats its class. No rule means the licence type is not permitted."""
    rules = LicenceTypeRule.objects.filter(licence_type=licence_type)
    if substance is not None:
        specific = _latest(rules.filter(substance=substance).first())
        if specific is not None:
            return specific
        substance_class = substance.substance_class
    if substance_class is None:
        return None
    return _latest(rules.filter(substance_class=substance_class).first())


def add_rule_version(
    rule: LicenceTypeRule,
    *,
    created_by: str,
    may_buy: bool,
    may_sell: bool,
    may_transport: bool,
    max_stock_qty: Decimal,
    max_per_transaction_qty: Decimal,
    validity_months: int,
) -> LicenceTypeRuleVersion:
    latest = _latest(rule)
    return LicenceTypeRuleVersion.objects.create(
        rule=rule,
        version=(latest.version + 1) if latest else 1,
        created_by=created_by,
        may_buy=may_buy,
        may_sell=may_sell,
        may_transport=may_transport,
        max_stock_qty=max_stock_qty,
        max_per_transaction_qty=max_per_transaction_qty,
        validity_months=validity_months,
    )
```

Add `"catalogue",` to `INSTALLED_APPS` in `backend/config/settings.py` (after `"identity",`), then run:
```bash
uv run --env-file .env.test python manage.py makemigrations catalogue
```
Expected: creates `catalogue/migrations/0001_initial.py`.

`backend/catalogue/migrations/0002_append_only_versions.py`:
```python
"""Rule versions are never edited: a change is a new version (spec D3)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalogue", "0001_initial"),
        ("core", "0001_app_role_privileges"),
    ]
    operations = [
        migrations.RunSQL(
            sql="REVOKE UPDATE, DELETE, TRUNCATE ON catalogue_licencetyperuleversion FROM gj_app;",
            reverse_sql="GRANT UPDATE, DELETE ON catalogue_licencetyperuleversion TO gj_app;",
        ),
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add catalogue/ config/settings.py tests/conftest.py tests/test_catalogue.py
git commit -m "feat: substance and licence-type catalogue with versioned, append-only rules"
```

---

### Task 3: Areas, positions and personnel assignments

**Files:**
- Create: `backend/positions/__init__.py`, `apps.py`, `models.py`, `service.py`, `migrations/__init__.py`
- Create (generated): `backend/positions/migrations/0001_initial.py`
- Modify: `backend/config/settings.py` (`INSTALLED_APPS`), `backend/tests/conftest.py`
- Test: `backend/tests/test_positions.py`

**Interfaces:**
- Consumes: `identity.models.User`, `identity.roles.Role.PERSONNEL`, `audit.service.record`.
- Produces: `AreaLevel` (`TALUKA`, `DISTRICT`, `STATE`); `Area(code, name, level, parent)`; `Position(code, title, level, area)`; `PersonnelAssignment(position, user, started_at, ended_at)`; `positions.service.covering_position(area: Area, level: str) -> Position | None`; `positions.service.assign(position: Position, user: User, *, by: str) -> PersonnelAssignment`; `positions.service.current_holder(position: Position) -> User | None`; `positions.service.positions_held(user: User) -> list[Position]`; conftest fixture `org` (a namespace with `state`, `ahmedabad`, `sanand`, `area_officer`, `district_officer`).

- [ ] **Step 1: Write the fixture and failing tests**

Add to `backend/tests/conftest.py` (imports at the top):
```python
from positions.models import Area, AreaLevel, Position


@pytest.fixture
def org(db):
    state = Area.objects.create(code="GJ", name="Gujarat", level=AreaLevel.STATE)
    ahmedabad = Area.objects.create(code="GJ-AHD", name="Ahmedabad", level=AreaLevel.DISTRICT, parent=state)
    sanand = Area.objects.create(code="GJ-AHD-SND", name="Sanand", level=AreaLevel.TALUKA, parent=ahmedabad)
    area_officer = Position.objects.create(
        code="AO-SND", title="Area Officer, Sanand", level=AreaLevel.TALUKA, area=sanand
    )
    district_officer = Position.objects.create(
        code="DO-AHD", title="District Officer, Ahmedabad", level=AreaLevel.DISTRICT, area=ahmedabad
    )
    return SimpleNamespace(
        state=state, ahmedabad=ahmedabad, sanand=sanand,
        area_officer=area_officer, district_officer=district_officer,
    )
```

`backend/tests/test_positions.py`:
```python
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from identity.roles import Role
from positions.models import AreaLevel, PersonnelAssignment
from positions.service import assign, covering_position, current_holder, positions_held

pytestmark = pytest.mark.django_db


def test_covering_position_at_same_level(app_db, org):
    assert covering_position(org.sanand, AreaLevel.TALUKA) == org.area_officer


def test_covering_position_walks_up_the_hierarchy(app_db, org):
    assert covering_position(org.sanand, AreaLevel.DISTRICT) == org.district_officer


def test_covering_position_none_when_level_has_no_position(app_db, org):
    assert covering_position(org.sanand, AreaLevel.STATE) is None


def test_assign_makes_user_the_holder(app_db, org, make_user, audit_actions):
    officer = make_user(role=Role.PERSONNEL)
    assign(org.area_officer, officer, by="test")
    assert current_holder(org.area_officer) == officer
    assert positions_held(officer) == [org.area_officer]
    assert audit_actions() == ["position.assigned"]


def test_transfer_moves_the_position_immediately(app_db, org, make_user):
    old, new = make_user(role=Role.PERSONNEL), make_user(role=Role.PERSONNEL)
    assign(org.area_officer, old, by="test")
    assign(org.area_officer, new, by="test")
    assert current_holder(org.area_officer) == new
    assert positions_held(old) == []
    assert positions_held(new) == [org.area_officer]


def test_only_personnel_can_hold_positions(app_db, org, make_user):
    with pytest.raises(ValueError, match="Authorised Personnel"):
        assign(org.area_officer, make_user(role=Role.LICENSEE), by="test")


def test_vacant_position_has_no_holder(app_db, org):
    assert current_holder(org.district_officer) is None


def test_database_allows_one_active_holder_per_position(app_db, org, make_user):
    assign(org.area_officer, make_user(role=Role.PERSONNEL), by="test")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PersonnelAssignment.objects.create(
                position=org.area_officer, user=make_user(role=Role.PERSONNEL), started_at=timezone.now()
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_positions.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'positions'`.

- [ ] **Step 3: Write the app**

`backend/positions/__init__.py`, `backend/positions/migrations/__init__.py`: empty.

`backend/positions/apps.py`:
```python
from django.apps import AppConfig


class PositionsConfig(AppConfig):
    name = "positions"
```

`backend/positions/models.py`:
```python
"""The authority hierarchy. Authority belongs to positions, not people (spec: positional authority).

An assignment says who holds a position and from when to when. A transfer ends one
assignment and starts another; the position and its approval chains never change.
"""

from django.db import models

from identity.models import User


class AreaLevel(models.TextChoices):
    TALUKA = "TALUKA", "Taluka / area"
    DISTRICT = "DISTRICT", "District"
    STATE = "STATE", "State"


class Area(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=16, choices=AreaLevel.choices)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")

    def __str__(self) -> str:
        return self.name


class Position(models.Model):
    code = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=120)
    level = models.CharField(max_length=16, choices=AreaLevel.choices)
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="positions")

    def __str__(self) -> str:
        return self.title


class PersonnelAssignment(models.Model):
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="assignments")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="assignments")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["position"],
                condition=models.Q(ended_at__isnull=True),
                name="one_active_holder_per_position",
            ),
        ]
```

`backend/positions/service.py`:
```python
"""Resolve positions by area and manage who currently holds them."""

from django.utils import timezone

from audit.service import record
from identity.models import User
from identity.roles import Role
from positions.models import Area, PersonnelAssignment, Position


def covering_position(area: Area, level: str) -> Position | None:
    """The position at `level` responsible for `area`, walking up to parent areas."""
    node = area
    while node is not None and node.level != level:
        node = node.parent
    if node is None:
        return None
    return Position.objects.filter(area=node, level=level).first()


def assign(position: Position, user: User, *, by: str) -> PersonnelAssignment:
    if user.role != Role.PERSONNEL:
        raise ValueError("Only Authorised Personnel can hold a position")
    now = timezone.now()
    PersonnelAssignment.objects.select_for_update().filter(
        position=position, ended_at__isnull=True
    ).update(ended_at=now)
    assignment = PersonnelAssignment.objects.create(position=position, user=user, started_at=now)
    record(
        action="position.assigned",
        actor=by,
        subject_type="position",
        subject_id=position.code,
        payload={"user_id": user.user_id},
    )
    return assignment


def current_holder(position: Position) -> User | None:
    assignment = (
        PersonnelAssignment.objects.select_related("user")
        .filter(position=position, ended_at__isnull=True)
        .first()
    )
    return assignment.user if assignment else None


def positions_held(user: User) -> list[Position]:
    return list(
        Position.objects.filter(assignments__user=user, assignments__ended_at__isnull=True).order_by("code")
    )
```

Add `"positions",` to `INSTALLED_APPS` (after `"catalogue",`), then run:
```bash
uv run --env-file .env.test python manage.py makemigrations positions
```
Expected: creates `positions/migrations/0001_initial.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add positions/ config/settings.py tests/conftest.py tests/test_positions.py
git commit -m "feat: area hierarchy, positions and personnel assignments with transfers"
```

---

### Task 4: Licence records, frozen permissions and `trading_permitted`

**Files:**
- Modify: `backend/core/db_context.py` (add `acting_as_system`)
- Modify: `backend/identity/models.py` (`User.licensee_gstin_index`, `UserManager.create_user`)
- Create (generated): `backend/identity/migrations/0005_user_licensee_gstin_index.py`
- Create: `backend/licensing/__init__.py`, `apps.py`, `models.py`, `service.py`, `migrations/__init__.py`
- Create (generated): `backend/licensing/migrations/0001_initial.py`
- Create: `backend/licensing/migrations/0002_rls_and_append_only.py`
- Modify: `backend/config/settings.py` (`INSTALLED_APPS`), `backend/tests/conftest.py`
- Test: `backend/tests/test_licensing.py`

**Interfaces:**
- Consumes: `core.crypto.encrypt/decrypt/blind_index`, `core.db_context.set_actor/current_actor/SYSTEM_ROLE`, `catalogue.service.resolve_rule`, `positions.models.Area`, `audit.service.record`.
- Produces:
  - `core.db_context.acting_as_system(job: str)`: a context manager that must be used inside `transaction.atomic()`, and restores the previous actor when it exits.
  - `User.licensee_gstin_index: str` (blank for non-licensees); `User.objects.create_user(*, role, password, contact, licensee_gstin_index="")`.
  - `LicenceStatus` (`ACTIVE`, `SUSPENDED`, `REVOKED`).
  - `Licence` (`number_encrypted`, `number_index`, `gstin_encrypted`, `gstin_index`, `holder_name`, `contact_encrypted`, `licence_type`, `substance`, `substance_class`, `area`, `status`, `created_at`; methods `number()`, `gstin()`, `contact()`, `scope_name()`).
  - `LicenceValidityPeriod(licence, starts_on, ends_on, recorded_at, recorded_by)`.
  - `LicencePermissionsSnapshot(licence, rule_version, may_buy, may_sell, may_transport, max_stock_qty, max_per_transaction_qty, taken_at)`.
  - `licensing.service`:
    - `LicenceNotPermitted`, `InvalidLicenceData` (both `Exception`)
    - `record_licence(*, number, gstin, holder_name, contact, licence_type, area, starts_on, ends_on, recorded_by, substance=None, substance_class=None) -> Licence`
    - `record_renewal(licence, *, starts_on, ends_on, recorded_by) -> LicenceValidityPeriod`
    - `set_status(licence, status, *, by: str, reason: str) -> None`
    - `current_permissions(licence) -> LicencePermissionsSnapshot`
    - `current_period(licence, on: date) -> LicenceValidityPeriod | None`
    - `trading_permitted(licence, on: date) -> bool`
    - `covers(licence, substance) -> bool`
    - `find_by_number(number: str) -> Licence | None`
  - Conftest fixture `make_licence(**kwargs) -> Licence`.

- [ ] **Step 1: Write the fixture and failing tests**

Add to `backend/tests/conftest.py` (imports at the top):
```python
from datetime import date
from itertools import count

from core.db_context import acting_as_system
from licensing.service import record_licence

DEMO_GSTIN = "99AAAAA0000A1Z5"  # state code 99 does not exist: can never match a real business


@pytest.fixture
def make_licence(catalogue, org):
    numbers = count(1)

    def _make(
        *, gstin=DEMO_GSTIN, licence_type=None, substance=None, substance_class=None,
        starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31),
        contact="+919800000101", holder_name="Sanand Test Traders",
    ):
        if substance is None and substance_class is None:
            substance_class = catalogue.spirits
        with acting_as_system("test"):
            return record_licence(
                number=f"GJ/TEST/{next(numbers):04d}", gstin=gstin, holder_name=holder_name,
                contact=contact, licence_type=licence_type or catalogue.retail, area=org.sanand,
                starts_on=starts_on, ends_on=ends_on, recorded_by="test",
                substance=substance, substance_class=substance_class,
            )

    return _make
```

`backend/tests/test_licensing.py`:
```python
from datetime import date
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction

from catalogue.models import LicenceType
from catalogue.service import add_rule_version
from core.db_context import acting_as_system, set_actor
from identity.roles import Role
from licensing.models import Licence, LicenceStatus, LicenceValidityPeriod
from licensing.service import (
    InvalidLicenceData,
    LicenceNotPermitted,
    covers,
    current_permissions,
    find_by_number,
    record_renewal,
    set_status,
    trading_permitted,
)
from tests.conftest import DEMO_GSTIN, _permissions

pytestmark = pytest.mark.django_db


def test_recorded_licence_freezes_rule_permissions(app_db, make_licence):
    licence = make_licence()
    with acting_as_system("test"):
        snapshot = current_permissions(licence)
    assert (snapshot.may_buy, snapshot.may_sell) == (True, True)
    assert snapshot.max_per_transaction_qty == Decimal("500")


def test_rule_change_does_not_touch_existing_licence(app_db, catalogue, make_licence):
    licence = make_licence()
    add_rule_version(catalogue.retail_rule, created_by="test", **_permissions(max_per_transaction_qty=Decimal("50")))
    with acting_as_system("test"):
        assert current_permissions(licence).max_per_transaction_qty == Decimal("500")


def test_renewal_takes_a_fresh_snapshot_of_the_latest_rule(app_db, catalogue, make_licence, audit_actions):
    licence = make_licence()
    add_rule_version(catalogue.retail_rule, created_by="test", **_permissions(max_per_transaction_qty=Decimal("50")))
    with acting_as_system("test"):
        record_renewal(licence, starts_on=date(2027, 1, 1), ends_on=date(2027, 12, 31), recorded_by="test")
        assert current_permissions(licence).max_per_transaction_qty == Decimal("50")
    assert audit_actions() == ["licence.recorded", "licence.renewal_recorded"]


def test_licence_type_without_rule_cannot_be_recorded(app_db, make_licence):
    manufacturer = LicenceType.objects.create(code="MANUFACTURER", name="Manufacturer")
    with pytest.raises(LicenceNotPermitted):
        make_licence(licence_type=manufacturer)


def test_refused_licence_leaves_no_partial_record(app_db, make_licence):
    manufacturer = LicenceType.objects.create(code="MANUFACTURER", name="Manufacturer")
    with pytest.raises(LicenceNotPermitted):
        make_licence(licence_type=manufacturer)
    with acting_as_system("test"):
        assert Licence.objects.count() == 0


def test_malformed_gstin_is_rejected(app_db, make_licence):
    with pytest.raises(InvalidLicenceData, match="GSTIN"):
        make_licence(gstin="NOT-A-GSTIN")


def test_period_must_end_after_it_starts(app_db, make_licence):
    with pytest.raises(InvalidLicenceData, match="end"):
        make_licence(starts_on=date(2026, 6, 1), ends_on=date(2026, 5, 31))


def test_identifiers_are_encrypted_at_rest(app_db, make_licence):
    licence = make_licence()
    with connection.cursor() as cursor:
        cursor.execute("SELECT number_encrypted, gstin_encrypted FROM licensing_licence WHERE id = %s", [licence.id])
        number_raw, gstin_raw = cursor.fetchone()
    assert "GJ/TEST" not in number_raw
    assert DEMO_GSTIN not in gstin_raw


def test_find_by_number_is_exact_but_forgiving_about_case_and_spaces(app_db, make_licence):
    licence = make_licence()
    with acting_as_system("test"):
        assert find_by_number("  gj/test/0001 ") == licence
        assert find_by_number("GJ/TEST/000") is None
        assert find_by_number("GJ/TEST") is None


@pytest.mark.parametrize(
    ("on", "expected"),
    [
        (date(2025, 12, 31), False),
        (date(2026, 1, 1), True),
        (date(2026, 12, 31), True),
        (date(2027, 1, 1), False),
    ],
)
def test_trading_permitted_follows_validity_period(app_db, make_licence, on, expected):
    licence = make_licence()
    with acting_as_system("test"):
        assert trading_permitted(licence, on) is expected


def test_gap_between_periods_is_not_permitted(app_db, make_licence):
    licence = make_licence()
    with acting_as_system("test"):
        record_renewal(licence, starts_on=date(2027, 3, 1), ends_on=date(2028, 2, 29), recorded_by="test")
        assert trading_permitted(licence, date(2027, 2, 1)) is False
        assert trading_permitted(licence, date(2027, 3, 1)) is True


@pytest.mark.parametrize("status", [LicenceStatus.SUSPENDED, LicenceStatus.REVOKED])
def test_suspended_or_revoked_licence_cannot_trade(app_db, make_licence, status):
    licence = make_licence()
    with acting_as_system("test"):
        set_status(licence, status, by="test", reason="inspection")
        assert trading_permitted(licence, date(2026, 6, 1)) is False


def test_covers_substance_directly_or_through_its_class(app_db, catalogue, make_licence):
    class_licence = make_licence()
    whisky_licence = make_licence(substance=catalogue.whisky)
    assert covers(class_licence, catalogue.rum)
    assert covers(whisky_licence, catalogue.whisky)
    assert not covers(whisky_licence, catalogue.rum)


def test_holder_sees_only_their_own_licences(app_db, make_licence, make_user):
    mine = make_licence()
    make_licence(gstin="99BBBBB1111B1Z5")
    holder = make_user(role=Role.LICENSEE)
    holder.licensee_gstin_index = mine.gstin_index
    holder.save(update_fields=["licensee_gstin_index"])
    with transaction.atomic():
        set_actor(user_id=holder.user_id, role=Role.LICENSEE)
        assert list(Licence.objects.all()) == [mine]
        assert LicenceValidityPeriod.objects.count() == 1


def test_anonymous_context_sees_no_licences(app_db, make_licence):
    make_licence()
    assert Licence.objects.count() == 0


def test_licensing_authority_sees_all_licences(app_db, make_licence):
    make_licence()
    make_licence(gstin="99BBBBB1111B1Z5")
    with transaction.atomic():
        set_actor(user_id="GJLAUSER0001", role=Role.LICENSING_AUTHORITY)
        assert Licence.objects.count() == 2


def test_licensee_cannot_record_a_licence(app_db, catalogue, org):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            set_actor(user_id="GJLICENSEE01", role=Role.LICENSEE)
            Licence.objects.create(
                number_encrypted="x", number_index="x" * 64, gstin_encrypted="x", gstin_index="y" * 64,
                holder_name="x", contact_encrypted="x", licence_type=catalogue.retail,
                substance_class=catalogue.spirits, area=org.sanand,
            )


def test_validity_periods_cannot_be_edited(app_db, make_licence):
    make_licence()
    with pytest.raises(DatabaseError, match="permission denied"):
        with transaction.atomic(), acting_as_system("test"):
            LicenceValidityPeriod.objects.update(ends_on=date(2099, 1, 1))


def test_acting_as_system_restores_previous_actor(app_db):
    from core.db_context import current_actor

    set_actor(user_id="GJLICENSEE01", role=Role.LICENSEE)
    with acting_as_system("test"):
        assert current_actor()[1] == "SYSTEM"
    assert current_actor() == ("GJLICENSEE01", "LICENSEE")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_licensing.py -v`
Expected: collection error, `ImportError: cannot import name 'acting_as_system'`.

- [ ] **Step 3: Add `acting_as_system` and the licensee link on User**

Append to `backend/core/db_context.py` (add `from collections.abc import Iterator` and `from contextlib import contextmanager` at the top):
```python
@contextmanager
def acting_as_system(job: str) -> Iterator[None]:
    """Briefly act as a named SYSTEM job, e.g. to match a licence during enrolment.

    Use only for reads or writes that genuinely cross owners, keep the block small, and
    return only the minimum data to the caller. The previous actor is restored afterwards.
    """
    previous_user, previous_role = current_actor()
    set_actor(user_id=job, role=SYSTEM_ROLE)
    try:
        yield
    finally:
        set_actor(user_id=previous_user or "", role=previous_role or "")
```

In `backend/identity/models.py`:
- Add this field to `User`, after `role`:
  ```python
  # Blind index of the licensee's GSTIN; links the account to its licences. Blank otherwise.
  licensee_gstin_index = models.CharField(max_length=64, blank=True, db_index=True)
  ```
- Replace `UserManager.create_user` with:
  ```python
  def create_user(
      self, *, role: str, password: str, contact: str, licensee_gstin_index: str = ""
  ) -> "User":
      user = self.model(role=role, licensee_gstin_index=licensee_gstin_index)
      user.set_contact(contact)
      user.set_password(password)
      user.save()
      return user
  ```

Run:
```bash
uv run --env-file .env.test python manage.py makemigrations identity --name user_licensee_gstin_index
```

- [ ] **Step 4: Write the licensing models**

`backend/licensing/__init__.py`, `backend/licensing/migrations/__init__.py`: empty.

`backend/licensing/apps.py`:
```python
from django.apps import AppConfig


class LicensingConfig(AppConfig):
    name = "licensing"
```

`backend/licensing/models.py`:
```python
"""Licence records, as issued by the authority's existing licensing process.

This platform records licences; it does not issue them. Validity periods and permission
snapshots are append-only: a renewal adds a period and a fresh snapshot.
"""

from django.db import models

from catalogue.models import LicenceType, LicenceTypeRuleVersion, Substance, SubstanceClass
from core import crypto
from positions.models import Area


class LicenceStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    REVOKED = "REVOKED", "Revoked"


class Licence(models.Model):
    number_encrypted = models.TextField()
    number_index = models.CharField(max_length=64, unique=True)
    gstin_encrypted = models.TextField()
    gstin_index = models.CharField(max_length=64, db_index=True)
    holder_name = models.CharField(max_length=200)
    contact_encrypted = models.TextField()
    licence_type = models.ForeignKey(LicenceType, on_delete=models.PROTECT)
    substance = models.ForeignKey(Substance, on_delete=models.PROTECT, null=True, blank=True)
    substance_class = models.ForeignKey(SubstanceClass, on_delete=models.PROTECT, null=True, blank=True)
    area = models.ForeignKey(Area, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=LicenceStatus.choices, default=LicenceStatus.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(substance__isnull=False, substance_class__isnull=True)
                    | models.Q(substance__isnull=True, substance_class__isnull=False)
                ),
                name="licence_exactly_one_scope",
            ),
        ]

    def number(self) -> str:
        return crypto.decrypt(self.number_encrypted)

    def gstin(self) -> str:
        return crypto.decrypt(self.gstin_encrypted)

    def contact(self) -> str:
        return crypto.decrypt(self.contact_encrypted)

    def scope_name(self) -> str:
        return (self.substance or self.substance_class).name


class LicenceValidityPeriod(models.Model):
    licence = models.ForeignKey(Licence, on_delete=models.PROTECT, related_name="validity_periods")
    starts_on = models.DateField()
    ends_on = models.DateField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(ends_on__gte=models.F("starts_on")), name="period_ends_after_start"),
        ]


class LicencePermissionsSnapshot(models.Model):
    """Frozen copy of the rule version in force when the licence (or a renewal) was recorded."""

    licence = models.ForeignKey(Licence, on_delete=models.PROTECT, related_name="permission_snapshots")
    rule_version = models.ForeignKey(LicenceTypeRuleVersion, on_delete=models.PROTECT)
    may_buy = models.BooleanField()
    may_sell = models.BooleanField()
    may_transport = models.BooleanField()
    max_stock_qty = models.DecimalField(max_digits=12, decimal_places=3)
    max_per_transaction_qty = models.DecimalField(max_digits=12, decimal_places=3)
    taken_at = models.DateTimeField(auto_now_add=True)
```

Add `"licensing",` to `INSTALLED_APPS` (after `"positions",`), then run:
```bash
uv run --env-file .env.test python manage.py makemigrations licensing
```

- [ ] **Step 5: Write the RLS and append-only migration**

`backend/licensing/migrations/0002_rls_and_append_only.py`:
```python
"""Who may see and change licence data.

- A licensee reads only licences whose GSTIN index matches their account.
- Licensing Authority, Head Authority, Software Owner and SYSTEM jobs read all licences.
- Only Licensing Authority and SYSTEM jobs write.
- Periods and snapshots are visible exactly when their licence is, and are append-only.
Personnel read access (for transactions routed to them) is added in plan D2.
"""

from django.db import migrations

READERS = "('LICENSING_AUTHORITY', 'HEAD_AUTHORITY', 'SOFTWARE_OWNER', 'SYSTEM')"
WRITERS = "('LICENSING_AUTHORITY', 'SYSTEM')"
ROLE = "current_setting('app.role', true)"
OWN_GSTIN = (
    "(SELECT licensee_gstin_index FROM identity_user "
    "WHERE user_id = current_setting('app.user_id', true) AND licensee_gstin_index <> '')"
)

FORWARD = f"""
ALTER TABLE licensing_licence ENABLE ROW LEVEL SECURITY;
CREATE POLICY licence_holder_read ON licensing_licence FOR SELECT TO gj_app
    USING (gstin_index = {OWN_GSTIN});
CREATE POLICY licence_authority_read ON licensing_licence FOR SELECT TO gj_app
    USING ({ROLE} IN {READERS});
CREATE POLICY licence_insert ON licensing_licence FOR INSERT TO gj_app
    WITH CHECK ({ROLE} IN {WRITERS});
CREATE POLICY licence_update ON licensing_licence FOR UPDATE TO gj_app
    USING ({ROLE} IN {WRITERS}) WITH CHECK ({ROLE} IN {WRITERS});
REVOKE DELETE, TRUNCATE ON licensing_licence FROM gj_app;

ALTER TABLE licensing_licencevalidityperiod ENABLE ROW LEVEL SECURITY;
CREATE POLICY period_read ON licensing_licencevalidityperiod FOR SELECT TO gj_app
    USING (licence_id IN (SELECT id FROM licensing_licence));
CREATE POLICY period_insert ON licensing_licencevalidityperiod FOR INSERT TO gj_app
    WITH CHECK ({ROLE} IN {WRITERS});
REVOKE UPDATE, DELETE, TRUNCATE ON licensing_licencevalidityperiod FROM gj_app;

ALTER TABLE licensing_licencepermissionssnapshot ENABLE ROW LEVEL SECURITY;
CREATE POLICY snapshot_read ON licensing_licencepermissionssnapshot FOR SELECT TO gj_app
    USING (licence_id IN (SELECT id FROM licensing_licence));
CREATE POLICY snapshot_insert ON licensing_licencepermissionssnapshot FOR INSERT TO gj_app
    WITH CHECK ({ROLE} IN {WRITERS});
REVOKE UPDATE, DELETE, TRUNCATE ON licensing_licencepermissionssnapshot FROM gj_app;
"""

BACKWARD = """
DROP POLICY snapshot_insert ON licensing_licencepermissionssnapshot;
DROP POLICY snapshot_read ON licensing_licencepermissionssnapshot;
ALTER TABLE licensing_licencepermissionssnapshot DISABLE ROW LEVEL SECURITY;
DROP POLICY period_insert ON licensing_licencevalidityperiod;
DROP POLICY period_read ON licensing_licencevalidityperiod;
ALTER TABLE licensing_licencevalidityperiod DISABLE ROW LEVEL SECURITY;
DROP POLICY licence_update ON licensing_licence;
DROP POLICY licence_insert ON licensing_licence;
DROP POLICY licence_authority_read ON licensing_licence;
DROP POLICY licence_holder_read ON licensing_licence;
ALTER TABLE licensing_licence DISABLE ROW LEVEL SECURITY;
GRANT UPDATE, DELETE ON licensing_licencevalidityperiod, licensing_licencepermissionssnapshot TO gj_app;
GRANT DELETE ON licensing_licence TO gj_app;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("licensing", "0001_initial"),
        ("identity", "0005_user_licensee_gstin_index"),
        ("core", "0001_app_role_privileges"),
    ]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]
```
The SQL is built only from the constants above. No user input ever reaches it, which is why an f-string is safe here. If ruff flags `S608`, add `# noqa: S608` on the `FORWARD = f"""` line with that justification.

- [ ] **Step 6: Write the service**

`backend/licensing/service.py`:
```python
"""Record licences issued by the existing process, and answer "may this licence trade?".

Writes need a Licensing Authority or SYSTEM context (row-level security enforces this).
"""

import re
from datetime import date

from django.db import transaction

from audit.service import record
from catalogue.models import LicenceType, Substance, SubstanceClass
from catalogue.service import resolve_rule
from core import crypto
from licensing.models import (
    Licence,
    LicencePermissionsSnapshot,
    LicenceStatus,
    LicenceValidityPeriod,
)
from positions.models import Area

GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


class LicenceNotPermitted(Exception):
    """No licence type rule allows this licence type for this substance or class."""


class InvalidLicenceData(Exception):
    pass


def _check_period(starts_on: date, ends_on: date) -> None:
    if ends_on < starts_on:
        raise InvalidLicenceData("The validity period must end on or after its start date")


def _snapshot(licence: Licence) -> LicencePermissionsSnapshot:
    version = resolve_rule(licence.licence_type, substance=licence.substance, substance_class=licence.substance_class)
    if version is None:
        raise LicenceNotPermitted(
            f"{licence.licence_type.name} licences are not permitted for {licence.scope_name()}"
        )
    return LicencePermissionsSnapshot.objects.create(
        licence=licence,
        rule_version=version,
        may_buy=version.may_buy,
        may_sell=version.may_sell,
        may_transport=version.may_transport,
        max_stock_qty=version.max_stock_qty,
        max_per_transaction_qty=version.max_per_transaction_qty,
    )


def record_licence(
    *,
    number: str,
    gstin: str,
    holder_name: str,
    contact: str,
    licence_type: LicenceType,
    area: Area,
    starts_on: date,
    ends_on: date,
    recorded_by: str,
    substance: Substance | None = None,
    substance_class: SubstanceClass | None = None,
) -> Licence:
    gstin = gstin.strip().upper()
    if not GSTIN_PATTERN.match(gstin):
        raise InvalidLicenceData("The GSTIN is not in the valid 15-character format")
    _check_period(starts_on, ends_on)
    with transaction.atomic():  # licence, snapshot and period exist together or not at all
        return _create_licence(
            number=number, gstin=gstin, holder_name=holder_name, contact=contact,
            licence_type=licence_type, area=area, starts_on=starts_on, ends_on=ends_on,
            recorded_by=recorded_by, substance=substance, substance_class=substance_class,
        )


def _create_licence(*, number, gstin, holder_name, contact, licence_type, area, starts_on, ends_on,
                    recorded_by, substance, substance_class) -> Licence:
    licence = Licence.objects.create(
        number_encrypted=crypto.encrypt(number.strip()),
        number_index=crypto.blind_index(number),
        gstin_encrypted=crypto.encrypt(gstin),
        gstin_index=crypto.blind_index(gstin),
        holder_name=holder_name,
        contact_encrypted=crypto.encrypt(contact),
        licence_type=licence_type,
        substance=substance,
        substance_class=substance_class,
        area=area,
    )
    _snapshot(licence)
    LicenceValidityPeriod.objects.create(
        licence=licence, starts_on=starts_on, ends_on=ends_on, recorded_by=recorded_by
    )
    record(action="licence.recorded", actor=recorded_by, subject_type="licence", subject_id=str(licence.id))
    return licence


def record_renewal(licence: Licence, *, starts_on: date, ends_on: date, recorded_by: str) -> LicenceValidityPeriod:
    _check_period(starts_on, ends_on)
    with transaction.atomic():
        _snapshot(licence)
        period = LicenceValidityPeriod.objects.create(
            licence=licence, starts_on=starts_on, ends_on=ends_on, recorded_by=recorded_by
        )
    record(
        action="licence.renewal_recorded",
        actor=recorded_by,
        subject_type="licence",
        subject_id=str(licence.id),
        payload={"starts_on": starts_on.isoformat(), "ends_on": ends_on.isoformat()},
    )
    return period


def set_status(licence: Licence, status: str, *, by: str, reason: str) -> None:
    licence.status = status
    licence.save(update_fields=["status"])
    record(
        action="licence.status_changed",
        actor=by,
        subject_type="licence",
        subject_id=str(licence.id),
        reason=reason,
        payload={"status": str(status)},
    )


def current_permissions(licence: Licence) -> LicencePermissionsSnapshot:
    return licence.permission_snapshots.order_by("-id").first()


def current_period(licence: Licence, on: date) -> LicenceValidityPeriod | None:
    """The period covering `on`, or else the most recent one (for display)."""
    periods = licence.validity_periods.order_by("-starts_on")
    return periods.filter(starts_on__lte=on, ends_on__gte=on).first() or periods.first()


def trading_permitted(licence: Licence, on: date) -> bool:
    if licence.status != LicenceStatus.ACTIVE:
        return False
    return licence.validity_periods.filter(starts_on__lte=on, ends_on__gte=on).exists()


def covers(licence: Licence, substance: Substance) -> bool:
    if licence.substance_id is not None:
        return licence.substance_id == substance.id
    return licence.substance_class_id == substance.substance_class_id


def find_by_number(number: str) -> Licence | None:
    """Exact match only (case and surrounding spaces ignored). No partial search exists."""
    return (
        Licence.objects.select_related("licence_type", "substance", "substance_class", "area")
        .filter(number_index=crypto.blind_index(number))
        .first()
    )
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add core/db_context.py identity/ licensing/ config/settings.py tests/conftest.py tests/test_licensing.py
git commit -m "feat: licence records with frozen permissions, validity periods, RLS and trading_permitted"
```

---

### Task 5: Licence-gated enrolment

**Files:**
- Create: `backend/licensing/enrolment.py`, `backend/licensing/serializers.py`, `backend/licensing/views.py`, `backend/licensing/urls.py`
- Modify: `backend/config/urls.py`, `backend/config/settings.py` (throttle rate)
- Test: `backend/tests/test_enrolment.py`

**Interfaces:**
- Consumes: `licensing.service.find_by_number`, `Licence`, `LicenceStatus`, `identity.otp.issue_for_subject/verify_subject`, `OtpPurpose.ENROL`, `acting_as_system`, `User.objects.create_user(..., licensee_gstin_index=...)`, `audit.service.record`.
- Produces: `licensing.enrolment.start_enrolment(*, licence_number: str, gstin: str) -> OtpChallenge | None`; `licensing.enrolment.complete_enrolment(*, challenge_id: str, code: str, password: str) -> User | None`. HTTP API:
  - `POST /api/enrolment/start` `{licence_number, gstin}` → 200 `{challenge_id}` | 401 `{"detail": ENROLMENT_FAILED}` | 429
  - `POST /api/enrolment/complete` `{challenge_id, code, password}` → 201 `{user_id}` | 400 `{"password": [...]}` | 401 | 429

`ENROLMENT_FAILED = "We could not verify these details. Check the licence number and GSTIN exactly as printed on your licence."`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_enrolment.py`:
```python
import pytest

from core.db_context import acting_as_system
from identity.models import User
from identity.roles import Role
from licensing.models import LicenceStatus
from licensing.service import set_status
from tests.conftest import DEMO_GSTIN

pytestmark = pytest.mark.django_db

STRONG = "a-strong-licensee-pass-7"
FAILED = {"detail": "We could not verify these details. Check the licence number and GSTIN exactly as printed on your licence."}


def start(client, number, gstin=DEMO_GSTIN, **extra):
    return client.post(
        "/api/enrolment/start", {"licence_number": number, "gstin": gstin, **extra}, content_type="application/json"
    )


def complete(client, challenge_id, code, password=STRONG):
    return client.post(
        "/api/enrolment/complete",
        {"challenge_id": challenge_id, "code": code, "password": password},
        content_type="application/json",
    )


def test_enrolment_creates_a_licensee_linked_to_the_gstin(app_db, client, make_licence, otp_outbox):
    licence = make_licence(contact="+919800000777")
    first = start(client, "GJ/TEST/0001")
    assert first.status_code == 200
    assert otp_outbox[-1][0] == "+919800000777"

    second = complete(client, first.json()["challenge_id"], otp_outbox[-1][1])
    assert second.status_code == 201
    user = User.objects.get(user_id=second.json()["user_id"])
    assert user.role == Role.LICENSEE
    assert user.licensee_gstin_index == licence.gstin_index
    assert user.get_contact() == "+919800000777"


def test_otp_always_goes_to_contact_on_file(app_db, client, make_licence, otp_outbox):
    make_licence(contact="+919800000777")
    start(client, "GJ/TEST/0001", contact="+919999999999")
    assert otp_outbox[-1][0] == "+919800000777"


def test_wrong_gstin_and_unknown_licence_look_identical(app_db, client, make_licence, otp_outbox):
    make_licence()
    wrong_gstin = start(client, "GJ/TEST/0001", gstin="99ZZZZZ9999Z1Z5")
    unknown = start(client, "GJ/NOPE/9999")
    assert wrong_gstin.status_code == unknown.status_code == 401
    assert wrong_gstin.json() == unknown.json() == FAILED
    assert otp_outbox == []


def test_suspended_licence_cannot_enrol(app_db, client, make_licence, otp_outbox):
    licence = make_licence()
    with acting_as_system("test"):
        set_status(licence, LicenceStatus.SUSPENDED, by="test", reason="inspection")
    assert start(client, "GJ/TEST/0001").json() == FAILED


def test_gstin_already_enrolled_cannot_enrol_again(app_db, client, make_licence, otp_outbox):
    make_licence()
    first = start(client, "GJ/TEST/0001")
    complete(client, first.json()["challenge_id"], otp_outbox[-1][1])
    assert start(client, "GJ/TEST/0001").json() == FAILED


def test_weak_password_is_rejected_without_using_up_the_otp(app_db, client, make_licence, otp_outbox):
    make_licence()
    challenge_id = start(client, "GJ/TEST/0001").json()["challenge_id"]
    code = otp_outbox[-1][1]
    weak = complete(client, challenge_id, code, password="short")
    assert weak.status_code == 400
    assert "password" in weak.json()
    assert complete(client, challenge_id, code).status_code == 201


def test_wrong_code_does_not_enrol(app_db, client, make_licence, otp_outbox):
    make_licence()
    challenge_id = start(client, "GJ/TEST/0001").json()["challenge_id"]
    code = otp_outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    assert complete(client, challenge_id, wrong).status_code == 401
    assert not User.objects.filter(role=Role.LICENSEE).exists()


def test_enrolment_is_rate_limited(app_db, client):
    statuses = [start(client, "GJ/NOPE/9999").status_code for _ in range(11)]
    assert statuses[10] == 429


def test_enrolment_is_audited(app_db, client, make_licence, otp_outbox, audit_actions):
    make_licence()
    start(client, "GJ/NOPE/9999")
    first = start(client, "GJ/TEST/0001")
    complete(client, first.json()["challenge_id"], otp_outbox[-1][1])
    assert audit_actions()[-3:] == ["enrolment.failed", "enrolment.otp_sent", "enrolment.completed"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_enrolment.py -v`
Expected: FAIL with 404 on `/api/enrolment/start`.

- [ ] **Step 3: Write the enrolment service**

`backend/licensing/enrolment.py`:
```python
"""Licence-gated enrolment: only a business already on record can create an account.

The user proves control by entering the code sent to the contact ON FILE for the licence.
Nothing in the request can change where the code goes. Failures all look the same, so the
endpoint cannot be used to discover which licences or GSTINs exist.
"""

from audit.service import record
from core import crypto
from core.db_context import acting_as_system
from identity import otp
from identity.models import OtpChallenge, OtpPurpose, User
from identity.roles import Role
from licensing.models import Licence, LicenceStatus
from licensing.service import find_by_number

SUBJECT_PREFIX = "gstin:"


def _already_enrolled(gstin_index: str) -> bool:
    return User.objects.filter(licensee_gstin_index=gstin_index).exists()


def start_enrolment(*, licence_number: str, gstin: str) -> OtpChallenge | None:
    with acting_as_system("enrolment"):
        licence = find_by_number(licence_number)
        matches = (
            licence is not None
            and licence.gstin_index == crypto.blind_index(gstin)
            and licence.status == LicenceStatus.ACTIVE
            and not _already_enrolled(licence.gstin_index)
        )
        if not matches:
            record(action="enrolment.failed", payload={"attempted": licence_number[:40]})
            return None
        contact = licence.contact()
        gstin_index = licence.gstin_index
        record(action="enrolment.otp_sent", subject_type="licence", subject_id=str(licence.id))
    return otp.issue_for_subject(
        subject=SUBJECT_PREFIX + gstin_index, contact=contact, purpose=OtpPurpose.ENROL
    )


def complete_enrolment(*, challenge_id: str, code: str, password: str) -> User | None:
    """The caller must validate the password BEFORE calling, so a weak password never uses up the code."""
    subject = otp.verify_subject(challenge_id=challenge_id, purpose=OtpPurpose.ENROL, code=code)
    if subject is None or not subject.startswith(SUBJECT_PREFIX):
        return None
    gstin_index = subject.removeprefix(SUBJECT_PREFIX)
    with acting_as_system("enrolment"):
        licence = Licence.objects.filter(gstin_index=gstin_index, status=LicenceStatus.ACTIVE).first()
        if licence is None or _already_enrolled(gstin_index):
            return None
        contact = licence.contact()
    user = User.objects.create_user(
        role=Role.LICENSEE, password=password, contact=contact, licensee_gstin_index=gstin_index
    )
    record(action="enrolment.completed", actor=user.user_id, subject_type="user", subject_id=user.user_id)
    return user
```

- [ ] **Step 4: Write serializers, views and URLs**

`backend/licensing/serializers.py`:
```python
"""Input validation for licensing endpoints."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers


class EnrolmentStartSerializer(serializers.Serializer):
    licence_number = serializers.CharField(max_length=40)
    gstin = serializers.CharField(max_length=15)


class EnrolmentCompleteSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")
    password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value
```

`backend/licensing/views.py`:
```python
"""HTTP endpoints for licensing. Thin: validate, call a service, respond."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from licensing.enrolment import complete_enrolment, start_enrolment
from licensing.serializers import EnrolmentCompleteSerializer, EnrolmentStartSerializer

ENROLMENT_FAILED = (
    "We could not verify these details. "
    "Check the licence number and GSTIN exactly as printed on your licence."
)


def _failed() -> Response:
    return Response({"detail": ENROLMENT_FAILED}, status=status.HTTP_401_UNAUTHORIZED)


@method_decorator(csrf_protect, name="dispatch")
class EnrolmentStartView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "enrolment"

    def post(self, request):
        data = EnrolmentStartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        challenge = start_enrolment(**data.validated_data)
        if challenge is None:
            return _failed()
        return Response({"challenge_id": str(challenge.public_id)})


@method_decorator(csrf_protect, name="dispatch")
class EnrolmentCompleteView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        data = EnrolmentCompleteSerializer(data=request.data)
        data.is_valid(raise_exception=True)  # weak password -> 400 before the code is used
        user = complete_enrolment(
            challenge_id=str(data.validated_data["challenge_id"]),
            code=data.validated_data["code"],
            password=data.validated_data["password"],
        )
        if user is None:
            return _failed()
        return Response({"user_id": user.user_id}, status=status.HTTP_201_CREATED)
```

`backend/licensing/urls.py`:
```python
from django.urls import path

from licensing import views

urlpatterns = [
    path("enrolment/start", views.EnrolmentStartView.as_view()),
    path("enrolment/complete", views.EnrolmentCompleteView.as_view()),
]
```

In `backend/config/urls.py`, add `path("api/", include("licensing.urls")),` to `urlpatterns`.

In `backend/config/settings.py`, change `DEFAULT_THROTTLE_RATES` to:
```python
    "DEFAULT_THROTTLE_RATES": {"login": "10/min", "otp": "10/min", "enrolment": "10/min"},
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
uv run ruff format . && uv run ruff check .
git add licensing/ config/ tests/test_enrolment.py
git commit -m "feat: licence-gated enrolment with OTP to the contact on file"
```

---

### Task 6: "My licences" and catalogue APIs (data for the permissions card)

**Files:**
- Modify: `backend/licensing/serializers.py`, `backend/licensing/views.py`, `backend/licensing/urls.py`
- Test: `backend/tests/test_licence_api.py`

**Interfaces:**
- Consumes: `identity.permissions.role_required`, `Role.LICENSEE`, `licensing.service.current_permissions/current_period/trading_permitted`, `catalogue.models.Substance`.
- Produces: `licensing.serializers.licence_card(licence: Licence, today: date) -> dict`. HTTP API:
  - `GET /api/licences/mine` (LICENSEE only) → 200 `[{licence_number, holder_name, licence_type, scope, unit, status, valid_from, valid_to, trading_permitted, may_buy, may_sell, may_transport, max_stock_qty, max_per_transaction_qty}]`
  - `GET /api/catalogue/substances` (any logged-in user) → 200 `[{code, name, substance_class, unit}]`

`unit` is the substance's unit, or `null` when the licence covers a whole class. Quantities are decimal strings such as `"500.000"`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_licence_api.py`:
```python
import pytest

from identity.models import User
from identity.roles import Role
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db


def log_in(client, user, otp_outbox):
    first = client.post(
        "/api/auth/login", {"user_id": user.user_id, "password": TEST_PASSWORD}, content_type="application/json"
    )
    client.post(
        "/api/auth/login/verify",
        {"challenge_id": first.json()["challenge_id"], "code": otp_outbox[-1][1]},
        content_type="application/json",
    )


def licensee_for(licence) -> User:
    return User.objects.create_user(
        role=Role.LICENSEE, password=TEST_PASSWORD, contact="+919800000999",
        licensee_gstin_index=licence.gstin_index,
    )


def test_licensee_sees_own_licence_card(app_db, client, catalogue, make_licence, otp_outbox):
    licence = make_licence(substance=catalogue.whisky)
    make_licence(gstin="99BBBBB1111B1Z5")
    log_in(client, licensee_for(licence), otp_outbox)

    cards = client.get("/api/licences/mine").json()
    assert len(cards) == 1
    card = cards[0]
    assert card["licence_number"] == "GJ/TEST/0001"
    assert card["licence_type"] == "Retail"
    assert card["scope"] == "Whisky"
    assert card["unit"] == "L"
    assert card["may_sell"] is True
    assert card["max_per_transaction_qty"] == "500.000"
    assert card["valid_from"] == "2026-01-01" and card["valid_to"] == "2026-12-31"
    assert set(card) == {
        "licence_number", "holder_name", "licence_type", "scope", "unit", "status", "valid_from",
        "valid_to", "trading_permitted", "may_buy", "may_sell", "may_transport",
        "max_stock_qty", "max_per_transaction_qty",
    }


@pytest.mark.parametrize("role", [Role.PERSONNEL, Role.LICENSING_AUTHORITY, Role.HEAD_AUTHORITY])
def test_only_licensees_have_my_licences(app_db, client, make_user, otp_outbox, role):
    log_in(client, make_user(role=role), otp_outbox)
    assert client.get("/api/licences/mine").status_code == 403


def test_my_licences_requires_login(app_db, client):
    assert client.get("/api/licences/mine").status_code == 403


def test_substance_list_for_logged_in_users(app_db, client, catalogue, make_user, otp_outbox):
    log_in(client, make_user(role=Role.LICENSEE), otp_outbox)
    body = client.get("/api/catalogue/substances").json()
    assert {"code": "WHISKY", "name": "Whisky", "substance_class": "Spirits", "unit": "L"} in body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --env-file .env.test pytest tests/test_licence_api.py -v`
Expected: FAIL with 404 on `/api/licences/mine`.

- [ ] **Step 3: Write the presenter, views and URLs**

Append to `backend/licensing/serializers.py` (imports at the top):
```python
from datetime import date

from licensing.models import Licence
from licensing.service import current_period, current_permissions, trading_permitted


def licence_card(licence: Licence, today: date) -> dict:
    """Everything the permissions card shows. Only ever called for the holder's own licences."""
    permissions = current_permissions(licence)
    period = current_period(licence, today)
    return {
        "licence_number": licence.number(),
        "holder_name": licence.holder_name,
        "licence_type": licence.licence_type.name,
        "scope": licence.scope_name(),
        "unit": licence.substance.unit if licence.substance else None,
        "status": licence.status,
        "valid_from": period.starts_on.isoformat() if period else None,
        "valid_to": period.ends_on.isoformat() if period else None,
        "trading_permitted": trading_permitted(licence, today),
        "may_buy": permissions.may_buy,
        "may_sell": permissions.may_sell,
        "may_transport": permissions.may_transport,
        "max_stock_qty": str(permissions.max_stock_qty),
        "max_per_transaction_qty": str(permissions.max_per_transaction_qty),
    }
```

Append to `backend/licensing/views.py` (imports at the top):
```python
from django.utils import timezone

from catalogue.models import Substance
from identity.permissions import role_required
from identity.roles import Role
from licensing.models import Licence
from licensing.serializers import licence_card


class MyLicencesView(APIView):
    permission_classes = [role_required(Role.LICENSEE)]

    def get(self, request):
        # Filtered here AND by row-level security (two independent checks).
        licences = Licence.objects.select_related(
            "licence_type", "substance", "substance_class"
        ).filter(gstin_index=request.user.licensee_gstin_index).order_by("id")
        today = timezone.localdate()
        return Response([licence_card(licence, today) for licence in licences])


class SubstanceListView(APIView):
    def get(self, request):
        substances = Substance.objects.select_related("substance_class").order_by("name")
        return Response(
            [
                {"code": s.code, "name": s.name, "substance_class": s.substance_class.name, "unit": s.unit}
                for s in substances
            ]
        )
```

In `backend/licensing/urls.py`, add:
```python
    path("licences/mine", views.MyLicencesView.as_view()),
    path("catalogue/substances", views.SubstanceListView.as_view()),
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --env-file .env.test pytest -v`
Expected: all pass.

- [ ] **Step 5: D1 acceptance, then commit**

Run:
```bash
uv run ruff format --check . && uv run ruff check .
uv run --env-file .env.test python manage.py makemigrations --check --dry-run
uv run --env-file .env.test pytest -v
```
Expected: clean, `No changes detected`, all pass.

```bash
git add licensing/ tests/test_licence_api.py
git commit -m "feat: my-licences permissions card and substance list APIs"
```

---

## Spec coverage (D1)

| Spec item | Task |
|---|---|
| §4 catalogue, licence types, rule versions, specific beats class, no rule means not permitted | 2 |
| §5 licence records, encrypted identifiers, blind-index exact lookup | 4 |
| §5 validity periods, recorded renewals, frozen permission snapshots | 4 |
| §5 `trading_permitted` (status plus period), `covers` | 4 |
| §3 positions (positional authority, transfers) | 3 |
| §3 enrolment (licence number + GSTIN + OTP to contact on file, `LICENSEE` role) | 1, 5 |
| §6 permissions card data | 6 |
| §9 access tests (licensee sees own only; LA reads all; licensee can't write) | 4, 6 |
| §5 transaction checks, §5a alerts, approval chain | **Plan D2** |
| §6–7 screens and UX | **Plan D3** |
| §6 demo tooling, seed, persona picker, SMS inbox, script, Playwright | **Plan D4** |
