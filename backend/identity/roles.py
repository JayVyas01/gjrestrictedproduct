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
