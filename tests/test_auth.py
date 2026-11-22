from fastapi.testclient import TestClient

from app.main import app


def test_private_routes_require_login_and_health_is_public(signed_in_client) -> None:
    visitor = TestClient(app)
    assert visitor.get("/health").status_code == 200
    assert visitor.get("/", follow_redirects=False).status_code == 303
    assert visitor.get("/api/overview").status_code == 401
    assert visitor.post("/chat", json={"message": "hi"}).status_code == 401
    assert signed_in_client.get("/").status_code == 200


def test_login_and_logout(signed_in_client) -> None:
    visitor = TestClient(app)
    assert visitor.post("/auth/login", json={"password": "wrong"}).status_code == 401
    assert visitor.get("/api/overview").status_code == 401
    assert signed_in_client.get("/api/overview").status_code == 200
    assert signed_in_client.post("/auth/logout").status_code == 200
    assert signed_in_client.get("/api/overview").status_code == 401


def test_tampered_session_is_rejected(signed_in_client) -> None:
    token = signed_in_client.cookies.get("mage_session")
    assert token
    signed_in_client.cookies.set("mage_session", token[:-1] + ("A" if token[-1] != "A" else "B"))
    assert signed_in_client.get("/api/overview").status_code == 401
