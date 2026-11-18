"""Small, budgeted OpenAI Responses API wrapper for fixed classification tasks."""

from datetime import datetime, timezone
import json

import httpx

from app.config import Settings
from app.storage import Store


class BudgetExceeded(RuntimeError):
    pass


class AIClient:
    def __init__(self, settings: Settings, store: Store, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.store = store
        self.client = client or httpx.Client(timeout=90)
        self._owns_client = client is None

    def __enter__(self) -> "AIClient":
        return self

    def __exit__(self, *_: object) -> None:
        if self._owns_client:
            self.client.close()

    def json_response(
        self, *, name: str, schema: dict, instructions: str, data: object,
        max_output_tokens: int = 2500,
    ) -> dict:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        payload_text = json.dumps(data, ensure_ascii=False)
        # Byte count is deliberately conservative for the local spending guard.
        estimated_input = max(100, len((payload_text + instructions).encode("utf-8")))
        reserve = (
            estimated_input * self.settings.input_usd_per_million
            + max_output_tokens * self.settings.output_usd_per_million
        ) / 1_000_000
        if not self.store.reserve_budget(month, reserve, self.settings.monthly_budget_usd):
            raise BudgetExceeded("Monthly OpenAI budget reached")
        try:
            response = self.client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json={
                    "model": self.settings.openai_model,
                    "store": False,
                    "reasoning": {"effort": "none"},
                    "instructions": instructions,
                    "input": payload_text,
                    "max_output_tokens": max_output_tokens,
                    "text": {"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
                },
            )
            response.raise_for_status()
            result = response.json()
            usage = result.get("usage", {})
            input_tokens = int(usage.get("input_tokens", estimated_input))
            output_tokens = int(usage.get("output_tokens", max_output_tokens))
            actual = (
                input_tokens * self.settings.input_usd_per_million
                + output_tokens * self.settings.output_usd_per_million
            ) / 1_000_000
            self.store.add_usage(month, input_tokens, output_tokens, actual - reserve)
            if result.get("status") != "completed":
                raise RuntimeError(f"OpenAI response status: {result.get('status')}")
            text_parts = [
                content["text"]
                for item in result.get("output", [])
                for content in item.get("content", [])
                if content.get("type") == "output_text"
            ]
            if not text_parts:
                raise RuntimeError("OpenAI returned no structured text")
            return json.loads("".join(text_parts))
        except httpx.HTTPStatusError as exc:
            if 400 <= exc.response.status_code < 500:
                self.store.add_usage(month, 0, 0, -reserve)
            raise
        except Exception:
            # Keep the reservation if the request's billing outcome is uncertain.
            raise


EMAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "importance": {"type": "string", "enum": ["important", "normal"]},
                    "summary": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["id", "importance", "summary", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

EMAIL_SCREEN_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "importance": {"type": "string", "enum": ["important", "normal"]},
                    "reason": {"type": "string"},
                },
                "required": ["id", "importance", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

NEWS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["url", "summary"],
                "additionalProperties": False,
            },
        },
        "digest": {"type": "string"},
    },
    "required": ["items", "digest"],
    "additionalProperties": False,
}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["subject", "body"],
    "additionalProperties": False,
}
