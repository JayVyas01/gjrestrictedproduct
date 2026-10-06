"""The fixed set of roles defined by the spec, and which roles share which powers.

Roles are an enum (not a table) because they are legally defined and must not be
changed at runtime. Every permission check refers to these names.
"""

from django.db import models


class Role(models.TextChoices):
    # What a licensee may buy, sell or transport comes from their licences, not their role.
    LICENSEE = "LICENSEE", "Licensee"
    PERSONNEL = "PERSONNEL", "Authorised Personnel"
    LICENSING_AUTHORITY = "LICENSING_AUTHORITY", "Licensing Authority"
    SOFTWARE_OWNER = "SOFTWARE_OWNER", "Software Owner"
    HEAD_AUTHORITY = "HEAD_AUTHORITY", "Head Authority"


# Spec rule 5: only these roles may create or reset Authorised Personnel accounts.
PERSONNEL_PROVISIONERS = frozenset({Role.SOFTWARE_OWNER, Role.HEAD_AUTHORITY})

# Roles allowed to read the full audit trail. Must match the RLS policy in audit migration 0002.
AUDIT_READERS = frozenset({Role.SOFTWARE_OWNER, Role.HEAD_AUTHORITY})


class LoginRole(models.TextChoices):
    """The role a person picks at sign-in. Officers (Role.PERSONNEL) sign in as Area Officer or
    Superintendent, decided by the position they currently hold (identity/login.py)."""

    PARTY = "PARTY", "Party"
    LICENSING_AUTHORITY = "LICENSING_AUTHORITY", "Licensing Authority"
    AREA_OFFICER = "AREA_OFFICER", "Area Officer"
    SUPERINTENDENT = "SUPERINTENDENT", "Superintendent"
    HEAD_AUTHORITY = "HEAD_AUTHORITY", "Head Authority"
    SOFTWARE_OWNER = "SOFTWARE_OWNER", "Software Owner"  # API only; not offered in the web app


# The account role each sign-in role needs.
ACCOUNT_ROLE = {
    LoginRole.PARTY: Role.LICENSEE,
    LoginRole.LICENSING_AUTHORITY: Role.LICENSING_AUTHORITY,
    LoginRole.AREA_OFFICER: Role.PERSONNEL,
    LoginRole.SUPERINTENDENT: Role.PERSONNEL,
    LoginRole.HEAD_AUTHORITY: Role.HEAD_AUTHORITY,
    LoginRole.SOFTWARE_OWNER: Role.SOFTWARE_OWNER,
}
