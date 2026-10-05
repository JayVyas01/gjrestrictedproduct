"""Create .env.demo from .env.demo.example with fresh random keys (`make demo-env`).

Standard library only, so it runs on the host before anything is installed. Never prints a
value, and leaves an existing .env.demo alone.
"""

import base64
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.demo.example"
TARGET = ROOT / ".env.demo"


def fresh(name: str) -> str:
    if name == "FIELD_ENCRYPTION_KEY":  # a Fernet key: 32 random bytes, URL-safe base64
        return base64.urlsafe_b64encode(os.urandom(32)).decode()
    return secrets.token_urlsafe(48)


def main() -> None:
    if TARGET.exists():
        print(".env.demo already exists; leaving it unchanged.")
        return
    lines = []
    for line in EXAMPLE.read_text().splitlines():
        name, sep, value = line.partition("=")
        if sep and not line.startswith("#") and value == "generate":
            line = f"{name}={fresh(name)}"
        lines.append(line)
    fd = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as out:
        out.write("\n".join(lines) + "\n")
    print("Created .env.demo with fresh keys.")


if __name__ == "__main__":
    sys.exit(main())
