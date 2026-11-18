"""Create the local encryption key used for OAuth tokens in Docker."""

import base64
import os
from pathlib import Path


def main() -> None:
    directory = Path(__file__).resolve().parent.parent / ".secrets"
    directory.mkdir(mode=0o700, exist_ok=True)
    key_file = directory / "token_key"
    if key_file.exists():
        print(f"Token encryption key already exists at {key_file}")
        return
    key = base64.urlsafe_b64encode(os.urandom(32))
    with key_file.open("xb") as handle:
        if os.name != "nt":
            key_file.chmod(0o600)
        handle.write(key)
    print(f"Created token encryption key at {key_file}")


if __name__ == "__main__":
    main()
