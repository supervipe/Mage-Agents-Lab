"""Single background worker. Start with: python -m app.worker"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import logging
import os
import time
from zoneinfo import ZoneInfo

from app.ai import AIClient
from app.config import get_settings
from app.email_workflow import sync_account
from app.news_workflow import RSS_FEEDS, RELEASE_REPOS, collect_news, make_daily_digest
from app.storage import Store


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@contextmanager
def single_instance(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+b") as handle:
        handle.seek(0)
        try:
            import msvcrt
            if handle.seek(0, 2) == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Another worker is already running") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def is_due(store: Store, name: str, interval: timedelta) -> bool:
    row = store.one("SELECT last_success, last_error, last_attempt FROM job_state WHERE name=?", (name,))
    if not row or not row["last_success"]:
        return not row or not row["last_attempt"] or datetime.fromisoformat(row["last_attempt"]) + timedelta(minutes=15) <= datetime.now(timezone.utc)
    if row["last_error"] and row["last_attempt"]:
        return datetime.fromisoformat(row["last_attempt"]) + timedelta(minutes=15) <= datetime.now(timezone.utc)
    return datetime.fromisoformat(row["last_success"]) + interval <= datetime.now(timezone.utc)


def run_job(store: Store, name: str, task) -> None:
    try:
        task()
        store.set_job(name, True)
        logger.info("%s completed", name)
    except Exception as exc:
        store.set_job(name, False, f"{type(exc).__name__}: {exc}")
        logger.exception("%s failed", name)


def tick(store: Store) -> None:
    settings = get_settings()
    with AIClient(settings, store) as ai:
        for account in settings.accounts:
            name = f"mail:{account}"
            if is_due(store, name, timedelta(minutes=settings.poll_minutes)):
                run_job(store, name, lambda account=account: sync_account(account, store, ai))
        if is_due(store, "news", timedelta(hours=6)):
            def news_job():
                count, errors = collect_news(store)
                if len(errors) == len(RSS_FEEDS) + len(RELEASE_REPOS) + 1:
                    raise RuntimeError("Every news source failed")
                return f"{count} relevant items; {len(errors)} source errors"
            run_job(store, "news", news_job)
        zone = os.getenv("TZ")
        local_now = datetime.now(ZoneInfo(zone)) if zone else datetime.now().astimezone()
        day = local_now.date().isoformat()
        if local_now.hour >= settings.digest_hour and not store.one("SELECT day FROM digests WHERE day=?", (day,)) and is_due(store, "digest", timedelta(days=1)):
            run_job(store, "digest", lambda: make_daily_digest(store, ai, day))


def main() -> None:
    settings = get_settings()
    store = Store(settings.database_path)
    with single_instance(settings.database_path.parent / "worker.lock"):
        logger.info("Worker started for %d Gmail account(s)", len(settings.accounts))
        while True:
            tick(store)
            time.sleep(60)


if __name__ == "__main__":
    main()
