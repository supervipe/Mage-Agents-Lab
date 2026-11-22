import base64
import hashlib
import json
import os

import pytest


@pytest.fixture(autouse=True)
def dashboard_auth(tmp_path, monkeypatch):
    salt = os.urandom(16)
    password_hash = hashlib.scrypt(b"test-dashboard-password", salt=salt, n=2**14, r=8, p=1)
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii")
    path = tmp_path / "dashboard_auth"
    path.write_text(json.dumps({
        "salt": encode(salt), "password_hash": encode(password_hash),
        "session_key": encode(os.urandom(32)),
    }), encoding="utf-8")
    monkeypatch.setenv("DASHBOARD_AUTH_FILE", str(path))


@pytest.fixture
def signed_in_client():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.post("/auth/login", json={"password": "test-dashboard-password"})
    assert response.status_code == 200
    return client
