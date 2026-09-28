"""Read configuration from environment variables.

Missing required values stop the process at startup instead of silently
falling back to an insecure default.
"""

import os


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
