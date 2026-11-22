"""Create a private password hash and signing key for the dashboard."""

import base64
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path


def main() -> None:
    path = Path(__file__).resolve().parent.parent / ".secrets" / "dashboard_auth"
    if path.exists():
        print(f"Dashboard credentials already exist at {path}; leaving them unchanged.")
        return
    password = getpass("New dashboard password (at least 16 characters): ")
    if len(password) < 16:
        raise SystemExit("Password must be at least 16 characters")
    if password != getpass("Confirm dashboard password: "):
        raise SystemExit("Passwords did not match")
    salt = os.urandom(16)
    password_hash = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii")
    config = {
        "salt": encode(salt), "password_hash": encode(password_hash),
        "session_key": encode(os.urandom(32)),
    }
    path.parent.mkdir(mode=0o700, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        json.dump(config, file)
    print(f"Created dashboard credentials at {path}")


if __name__ == "__main__":
    main()
