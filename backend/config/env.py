"""Read configuration from environment variables.

Missing required values stop the process at startup instead of silently
falling back to an insecure default.
"""

import os
import re

# What DRF's throttles understand: a count, then a period starting s, m, h or d.
_RATE = re.compile(r"[0-9]+/(s|sec|second|m|min|minute|h|hour|d|day)")


class MissingSetting(RuntimeError):
    pass


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingSetting(f"Environment variable {name} must be set")
    return value


def optional(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes"}


def listed(name: str) -> list[str]:
    return [item.strip() for item in required(name).split(",") if item.strip()]


def count(name: str, default: int) -> int:
    """A whole number of 0 or more; anything else stops the process."""
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    if not (value.isascii() and value.isdigit()):
        raise MissingSetting(f"Environment variable {name} must be a whole number of 0 or more")
    return int(value)


def rate(name: str, default: str) -> str:
    """A throttle rate such as 10/min; anything DRF would not understand stops the process."""
    value = optional(name, default)
    if not _RATE.fullmatch(value):
        raise MissingSetting(f"Environment variable {name} must be a rate like 10/min")
    return value
