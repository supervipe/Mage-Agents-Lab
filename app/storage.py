from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=30000")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS email_items (
                    account TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    importance TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (account, provider_id)
                );
                CREATE INDEX IF NOT EXISTS email_recent ON email_items(received_at DESC);
                CREATE TABLE IF NOT EXISTS news_items (
                    url TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS news_recent ON news_items(published_at DESC);
                CREATE TABLE IF NOT EXISTS drafts (
                    id TEXT PRIMARY KEY,
                    account TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    provider_id TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS digests (
                    day TEXT PRIMARY KEY,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_state (
                    name TEXT PRIMARY KEY,
                    last_success TEXT,
                    last_error TEXT,
                    last_attempt TEXT
                );
                CREATE TABLE IF NOT EXISTS usage (
                    month TEXT PRIMARY KEY,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_usd REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS cursors (
                    account TEXT PRIMARY KEY,
                    history_id TEXT NOT NULL
                );
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(job_state)")}
            if "last_attempt" not in columns:
                db.execute("ALTER TABLE job_state ADD COLUMN last_attempt TEXT")

    def rows(self, query: str, params: tuple = ()) -> list[dict]:
        with self.connection() as db:
            return [dict(row) for row in db.execute(query, params)]

    def one(self, query: str, params: tuple = ()) -> dict | None:
        rows = self.rows(query, params)
        return rows[0] if rows else None

    def cursor(self, account: str) -> str | None:
        row = self.one("SELECT history_id FROM cursors WHERE account=?", (account,))
        return row["history_id"] if row else None

    def set_cursor(self, account: str, history_id: str) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO cursors VALUES (?, ?) ON CONFLICT(account) DO UPDATE SET history_id=excluded.history_id",
                (account, history_id),
            )

    def existing_email_ids(self, account: str, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        placeholders = ",".join("?" for _ in ids)
        rows = self.rows(
            f"SELECT provider_id FROM email_items WHERE account=? AND provider_id IN ({placeholders})",
            (account, *ids),
        )
        return {row["provider_id"] for row in rows}

    def save_emails(self, items: list[dict]) -> None:
        with self.connection() as db:
            db.executemany(
                """INSERT OR IGNORE INTO email_items
                (account, provider_id, thread_id, sender, subject, received_at,
                 importance, summary, reason, url, created_at)
                VALUES (:account, :provider_id, :thread_id, :sender, :subject,
                        :received_at, :importance, :summary, :reason, :url, :created_at)""",
                items,
            )

    def save_news(self, items: list[dict]) -> None:
        with self.connection() as db:
            db.executemany(
                """INSERT OR IGNORE INTO news_items
                (url, title, source, published_at, excerpt, score, created_at)
                VALUES (:url, :title, :source, :published_at, :excerpt, :score, :created_at)""",
                items,
            )

    def save_news_summaries(self, items: list[tuple[str, str]]) -> None:
        with self.connection() as db:
            db.executemany("UPDATE news_items SET summary=? WHERE url=?", items)

    def create_draft(self, account: str, recipient: str, subject: str, body: str) -> dict:
        draft = {
            "id": str(uuid4()), "account": account, "recipient": recipient,
            "subject": subject, "body": body, "status": "draft", "created_at": now_utc(),
        }
        with self.connection() as db:
            db.execute(
                """INSERT INTO drafts (id, account, recipient, subject, body, status, created_at)
                VALUES (:id, :account, :recipient, :subject, :body, :status, :created_at)""",
                draft,
            )
        return draft

    def claim_draft(self, draft_id: str) -> dict | None:
        with self.connection() as db:
            cursor = db.execute(
                "UPDATE drafts SET status='sending' WHERE id=? AND status='draft'", (draft_id,)
            )
            if cursor.rowcount != 1:
                return None
            return dict(db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone())

    def finish_draft(self, draft_id: str, status: str, provider_id: str = "", error: str = "") -> None:
        with self.connection() as db:
            db.execute(
                "UPDATE drafts SET status=?, sent_at=?, provider_id=?, error=? WHERE id=? AND status='sending'",
                (status, now_utc() if status == "sent" else None, provider_id, error, draft_id),
            )

    def set_job(self, name: str, success: bool, error: str = "") -> None:
        with self.connection() as db:
            db.execute(
                """INSERT INTO job_state(name, last_success, last_error, last_attempt) VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                  last_success=CASE WHEN excluded.last_success IS NOT NULL THEN excluded.last_success ELSE job_state.last_success END,
                  last_error=excluded.last_error,
                  last_attempt=excluded.last_attempt""",
                (name, now_utc() if success else None, error[:300], now_utc()),
            )

    def usage_usd(self, month: str) -> float:
        row = self.one("SELECT estimated_usd FROM usage WHERE month=?", (month,))
        return float(row["estimated_usd"]) if row else 0.0

    def add_usage(self, month: str, input_tokens: int, output_tokens: int, cost: float) -> None:
        with self.connection() as db:
            db.execute(
                """INSERT INTO usage VALUES (?, ?, ?, ?)
                ON CONFLICT(month) DO UPDATE SET
                  input_tokens=input_tokens+excluded.input_tokens,
                  output_tokens=output_tokens+excluded.output_tokens,
                  estimated_usd=estimated_usd+excluded.estimated_usd""",
                (month, input_tokens, output_tokens, cost),
            )

    def reserve_budget(self, month: str, estimate: float, limit: float) -> bool:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT estimated_usd FROM usage WHERE month=?", (month,)).fetchone()
            spent = float(row[0]) if row else 0.0
            if spent + estimate > limit:
                return False
            db.execute(
                """INSERT INTO usage(month, estimated_usd) VALUES (?, ?)
                ON CONFLICT(month) DO UPDATE SET estimated_usd=estimated_usd+excluded.estimated_usd""",
                (month, estimate),
            )
            return True
