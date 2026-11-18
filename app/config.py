from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    accounts: tuple[str, ...]
    database_path: Path
    openai_api_key: str
    openai_model: str
    monthly_budget_usd: float
    input_usd_per_million: float
    output_usd_per_million: float
    digest_hour: int
    poll_minutes: int


def get_settings() -> Settings:
    accounts = tuple(
        item.strip().lower()
        for item in os.getenv("GMAIL_ACCOUNTS", "").split(",")
        if item.strip()
    )
    return Settings(
        accounts=accounts,
        database_path=Path(os.getenv("DATABASE_PATH", ".data/agents.sqlite3")),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
        monthly_budget_usd=float(os.getenv("MONTHLY_BUDGET_USD", "5")),
        input_usd_per_million=float(os.getenv("INPUT_USD_PER_MILLION", "0.10")),
        output_usd_per_million=float(os.getenv("OUTPUT_USD_PER_MILLION", "0.50")),
        digest_hour=int(os.getenv("DIGEST_HOUR", "8")),
        poll_minutes=int(os.getenv("POLL_MINUTES", "10")),
    )
