"""Gmail OAuth and message access for a single personal account."""

import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
from urllib.parse import quote

import httpx

from app.token_store import get_token, set_token


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"br", "p", "div", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _decode_body(payload: dict) -> str:
    found: dict[str, str] = {}

    def visit(part: dict) -> None:
        mime = part.get("mimeType", "")
        encoded = part.get("body", {}).get("data")
        if encoded and mime in {"text/plain", "text/html"}:
            raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            charset = "utf-8"
            for header in part.get("headers", []):
                if header.get("name", "").lower() == "content-type" and "charset=" in header.get("value", ""):
                    charset = header["value"].split("charset=", 1)[1].split(";", 1)[0].strip(' "')
            found.setdefault(mime, raw.decode(charset, errors="replace"))
        for child in part.get("parts", []):
            visit(child)

    visit(payload)
    if "text/plain" in found:
        return found["text/plain"]
    if "text/html" in found:
        parser = _TextExtractor()
        parser.feed(found["text/html"])
        return unescape("".join(parser.parts))
    return ""


def parse_message(account: str, data: dict) -> dict:
    headers = {
        header.get("name", "").lower(): header.get("value", "")
        for header in data.get("payload", {}).get("headers", [])
    }
    timestamp = datetime.fromtimestamp(int(data.get("internalDate", "0")) / 1000, timezone.utc)
    thread_id = data.get("threadId", data["id"])
    return {
        "account": account,
        "provider_id": data["id"],
        "thread_id": thread_id,
        "sender": headers.get("from", ""),
        "subject": headers.get("subject", "(no subject)"),
        "received_at": timestamp.isoformat(),
        "body": _decode_body(data.get("payload", {}))[:4000],
        "url": f"https://mail.google.com/mail/?authuser={quote(account)}#all/{thread_id}",
    }


def connect_account(client_secrets: Path, expected_email: str) -> str:
    """Run Google's installed-app flow and save the resulting token locally."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
    open_browser = os.getenv("OAUTH_OPEN_BROWSER", "1") != "0"
    credentials = flow.run_local_server(
        host="127.0.0.1", port=0, open_browser=open_browser,
        prompt="consent", access_type="offline",
    )
    with httpx.Client(timeout=30) as client:
        response = client.get(
            f"{BASE_URL}/profile",
            headers={"Authorization": f"Bearer {credentials.token}"},
        )
        response.raise_for_status()
    actual_email = response.json()["emailAddress"].lower()
    if actual_email != expected_email.lower():
        raise ValueError(f"Signed in as {actual_email}; expected {expected_email}. Token was not saved.")
    if not credentials.refresh_token:
        raise RuntimeError("Google did not provide an offline refresh token. Token was not saved.")
    set_token(actual_email, credentials.to_json())
    return actual_email


class GmailClient:
    def __init__(self, account: str, client: httpx.Client | None = None) -> None:
        self.account = account.lower()
        self.client = client or httpx.Client(timeout=30)
        self._owns_client = client is None

    def __enter__(self) -> "GmailClient":
        return self

    def __exit__(self, *_: object) -> None:
        if self._owns_client:
            self.client.close()

    def _token(self) -> str:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        token_json = get_token(self.account)
        if not token_json:
            raise RuntimeError(f"Gmail account {self.account} is not connected")
        credentials = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        if not credentials.valid:
            credentials.refresh(Request())
            set_token(self.account, credentials.to_json())
        return credentials.token

    def _request(self, method: str, path: str, **kwargs: object) -> dict:
        response = self.client.request(
            method,
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bearer {self._token()}"},
            **kwargs,
        )
        response.raise_for_status()
        return response.json()

    def profile(self) -> dict:
        return self._request("GET", "/profile")

    def recent_ids(self, query: str = "newer_than:7d") -> list[str]:
        ids: list[str] = []
        page: str | None = None
        while True:
            params = {"q": query, "labelIds": "INBOX", "maxResults": 100}
            if page:
                params["pageToken"] = page
            data = self._request("GET", "/messages", params=params)
            ids.extend(item["id"] for item in data.get("messages", []))
            page = data.get("nextPageToken")
            if len(ids) >= 5000 and page:
                raise RuntimeError("Gmail catch-up exceeded 5,000 messages; cursor was not advanced")
            if not page:
                return ids

    def changed_ids(self, history_id: str) -> tuple[list[str], str]:
        ids: set[str] = set()
        page: str | None = None
        latest = history_id
        while True:
            params = {"startHistoryId": history_id, "historyTypes": "messageAdded", "maxResults": 500}
            if page:
                params["pageToken"] = page
            data = self._request("GET", "/history", params=params)
            latest = data.get("historyId", latest)
            for event in data.get("history", []):
                ids.update(item["message"]["id"] for item in event.get("messagesAdded", []))
            page = data.get("nextPageToken")
            if not page:
                return list(ids), latest

    def message(self, message_id: str) -> dict | None:
        try:
            data = self._request("GET", f"/messages/{message_id}", params={"format": "full"})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        if "INBOX" not in data.get("labelIds", []):
            return None
        return parse_message(self.account, data)

    def send(self, recipient: str, subject: str, body: str) -> str:
        message = EmailMessage()
        message["To"] = recipient
        message["From"] = self.account
        message["Subject"] = subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        result = self._request("POST", "/messages/send", json={"raw": raw})
        return result["id"]
