from dataclasses import replace
import base64
from email import message_from_bytes
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import AIClient, BudgetExceeded, DRAFT_SCHEMA
from app.config import get_settings
from app.email_workflow import sync_account
from app.gmail import GmailClient, parse_message
from app.main import app
from app.news_workflow import _rss_items
from app.storage import Store
from app.token_store import get_token, set_token
from app.worker import is_due
from datetime import timedelta


def test_draft_is_claimed_once(tmp_path) -> None:
    store = Store(tmp_path / "db.sqlite3")
    draft = store.create_draft("a@gmail.com", "b@example.com", "Hello", "Body")
    assert store.claim_draft(draft["id"])["status"] == "sending"
    assert store.claim_draft(draft["id"]) is None
    store.finish_draft(draft["id"], "sent", provider_id="gmail-id")
    assert store.one("SELECT status, provider_id FROM drafts WHERE id=?", (draft["id"],)) == {
        "status": "sent", "provider_id": "gmail-id"
    }


def test_email_sync_advances_cursor_only_after_classification(tmp_path, monkeypatch) -> None:
    store = Store(tmp_path / "db.sqlite3")

    class FakeGmail:
        def __init__(self, account):
            self.account = account
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def profile(self):
            return {"historyId": "cursor-1"}
        def recent_ids(self, query="newer_than:7d"):
            return ["m1", "m2"]
        def changed_ids(self, cursor):
            assert cursor == "cursor-1"
            return [], "cursor-2"
        def message(self, message_id):
            return {
                "account": self.account, "provider_id": message_id, "thread_id": message_id,
                "sender": "friend@example.com" if message_id == "m1" else "shop@example.com",
                "subject": "Need your answer" if message_id == "m1" else "Weekly sale",
                "received_at": "2026-11-16T12:00:00+00:00",
                "body": "Please reply" if message_id == "m1" else "Private promotional content",
                "url": "https://mail.google.com/test",
            }

    class FakeAI:
        def json_response(self, **kwargs):
            if kwargs["name"] == "email_screen":
                assert all("body" not in item for item in kwargs["data"])
                return {"items": [
                    {"id": "m1", "importance": "important", "reason": "May need a reply"},
                    {"id": "m2", "importance": "normal", "reason": "Promotion"},
                ]}
            assert kwargs["name"] == "email_triage"
            assert len(kwargs["data"]) == 1
            assert kwargs["data"][0]["body"] == "Please reply"
            return {"items": [{"id": "m1", "importance": "important", "summary": "Needs a reply.", "reason": "Action requested"}]}

    monkeypatch.setattr("app.email_workflow.GmailClient", FakeGmail)
    assert sync_account("a@gmail.com", store, FakeAI()) == 2
    assert store.cursor("a@gmail.com") == "cursor-1"
    assert sync_account("a@gmail.com", store, FakeAI()) == 0
    assert store.cursor("a@gmail.com") == "cursor-2"
    assert store.one("SELECT summary FROM email_items WHERE provider_id='m1'")["summary"] == "Needs a reply."
    assert store.one("SELECT summary FROM email_items WHERE provider_id='m2'")["summary"] == ""


def test_budget_reservation_blocks_next_model_call(tmp_path) -> None:
    store = Store(tmp_path / "db.sqlite3")
    settings = replace(
        get_settings(), openai_api_key="test-key", monthly_budget_usd=0.0002,
        input_usd_per_million=0.1, output_usd_per_million=0.5,
    )
    def respond(request):
        assert request.url.path == "/v1/responses"
        payload = json.loads(request.content)
        assert payload["store"] is False
        return httpx.Response(200, json={
            "status": "completed", "usage": {"input_tokens": 100, "output_tokens": 20},
            "output": [{"content": [{"type": "output_text", "text": '{"subject":"Hi","body":"Hello"}'}]}],
        })
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        with AIClient(settings, store, http) as ai:
            assert ai.json_response(name="draft", schema=DRAFT_SCHEMA, instructions="Write", data={}, max_output_tokens=100)["subject"] == "Hi"
            with pytest.raises(BudgetExceeded):
                ai.json_response(name="draft", schema=DRAFT_SCHEMA, instructions="Write", data={}, max_output_tokens=1000)


def test_dashboard_approves_draft_only_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "dashboard.sqlite3"))
    monkeypatch.setenv("GMAIL_ACCOUNTS", "a@gmail.com")
    monkeypatch.setattr("app.api.dashboard.get_token", lambda *_: "connected")
    sent = []
    def fake_send(self, recipient, subject, body):
        sent.append((self.account, recipient, subject, body))
        return "gmail-id"
    monkeypatch.setattr("app.gmail.GmailClient.send", fake_send)
    client = TestClient(app)
    token = client.get("/api/overview").json()["csrf_token"]
    headers = {"X-CSRF-Token": token}
    draft = client.post("/api/drafts", headers=headers, json={
        "account": "a@gmail.com", "recipient": "b@example.com",
        "subject": "Hello", "body": "Message",
    })
    assert draft.status_code == 200
    draft_id = draft.json()["id"]
    assert client.post(f"/api/drafts/{draft_id}/approve").status_code == 403
    assert client.post(f"/api/drafts/{draft_id}/approve", headers=headers).status_code == 200
    assert client.post(f"/api/drafts/{draft_id}/approve", headers=headers).status_code == 409
    assert sent == [("a@gmail.com", "b@example.com", "Hello", "Message")]


def test_rss_parser_keeps_direct_source_link() -> None:
    xml = """<rss><channel><item><title>New AI agent framework</title>
    <link>https://example.com/article</link><pubDate>Mon, 16 Nov 2026 12:00:00 GMT</pubDate>
    <description>Release details</description></item></channel></rss>"""
    items = _rss_items(xml, "Example")
    assert len(items) == 1
    assert items[0]["url"] == "https://example.com/article"
    assert items[0]["score"] > 0


def test_gmail_message_parsing_and_send_format(monkeypatch) -> None:
    raw_body = base64.urlsafe_b64encode(b"Please reply tomorrow.").decode()
    parsed = parse_message("a@gmail.com", {
        "id": "m1", "threadId": "t1", "internalDate": "1794830400000",
        "payload": {
            "headers": [{"name": "From", "value": "Friend <b@example.com>"}, {"name": "Subject", "value": "Meeting"}],
            "mimeType": "text/plain", "body": {"data": raw_body},
        },
    })
    assert parsed["body"] == "Please reply tomorrow."
    assert parsed["subject"] == "Meeting"
    assert "authuser=a%40gmail.com" in parsed["url"]

    def respond(request):
        assert request.url.path.endswith("/messages/send")
        message = message_from_bytes(base64.urlsafe_b64decode(json.loads(request.content)["raw"]))
        assert message["To"] == "b@example.com"
        assert message["From"] == "a@gmail.com"
        assert message["Subject"] == "Hello"
        assert message.get_payload(decode=True).decode().strip() == "Message"
        return httpx.Response(200, json={"id": "sent-1"})
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        gmail = GmailClient("a@gmail.com", http)
        monkeypatch.setattr(gmail, "_token", lambda: "fake-token")
        assert gmail.send("b@example.com", "Hello", "Message") == "sent-1"


def test_failed_job_waits_before_retry(tmp_path) -> None:
    store = Store(tmp_path / "db.sqlite3")
    assert is_due(store, "mail:a@gmail.com", timedelta(minutes=10))
    store.set_job("mail:a@gmail.com", False, "temporary failure")
    assert not is_due(store, "mail:a@gmail.com", timedelta(minutes=10))


def test_encrypted_file_tokens_are_persistent_and_not_plaintext(tmp_path, monkeypatch) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setenv("TOKEN_STORE_BACKEND", "encrypted_file")
    monkeypatch.setenv("TOKEN_STORE_DIR", str(tmp_path / "tokens"))
    key_file = tmp_path / "token_key"
    key_file.write_bytes(Fernet.generate_key())
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY_FILE", str(key_file))

    assert get_token("a@gmail.com") is None
    set_token("A@GMAIL.COM", '{"refresh_token":"private-value"}')
    assert get_token("a@gmail.com") == '{"refresh_token":"private-value"}'
    saved = list((tmp_path / "tokens").glob("*.token"))
    assert len(saved) == 1
    assert b"private-value" not in saved[0].read_bytes()
