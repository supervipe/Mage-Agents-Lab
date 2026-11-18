"""OAuth token storage for native Windows and Linux containers."""

from hashlib import sha256
import os
from pathlib import Path
from uuid import uuid4


KEYRING_SERVICE = "mage-agents-lab-gmail"


def _backend() -> str:
    backend = os.getenv("TOKEN_STORE_BACKEND", "keyring")
    if backend not in {"keyring", "encrypted_file"}:
        raise ValueError(f"Unsupported TOKEN_STORE_BACKEND: {backend}")
    return backend


def _cipher():
    from cryptography.fernet import Fernet

    key_file = os.getenv("TOKEN_ENCRYPTION_KEY_FILE")
    if key_file:
        key = Path(key_file).read_bytes().strip()
    else:
        key = os.getenv("TOKEN_ENCRYPTION_KEY", "").encode()
    if not key:
        raise RuntimeError("Encrypted token storage needs TOKEN_ENCRYPTION_KEY_FILE or TOKEN_ENCRYPTION_KEY")
    return Fernet(key)


def _token_path(account: str) -> Path:
    from app.config import get_settings

    directory = Path(os.getenv("TOKEN_STORE_DIR", str(get_settings().database_path.parent / "tokens")))
    digest = sha256(account.lower().encode()).hexdigest()
    return directory / f"{digest}.token"


def get_token(account: str) -> str | None:
    if _backend() == "keyring":
        import keyring

        return keyring.get_password(KEYRING_SERVICE, account.lower())
    path = _token_path(account)
    if not path.exists():
        return None
    return _cipher().decrypt(path.read_bytes()).decode("utf-8")


def set_token(account: str, token_json: str) -> None:
    if _backend() == "keyring":
        import keyring

        keyring.set_password(KEYRING_SERVICE, account.lower(), token_json)
        return
    path = _token_path(account)
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.parent.chmod(0o700)
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            if os.name != "nt":
                temporary.chmod(0o600)
            handle.write(_cipher().encrypt(token_json.encode("utf-8")))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
