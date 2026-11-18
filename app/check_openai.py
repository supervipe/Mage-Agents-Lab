"""Small, nonprivate OpenAI integration check. No email is sent."""

import httpx

from app.ai import AIClient, DRAFT_SCHEMA
from app.config import get_settings
from app.storage import Store


def main() -> None:
    settings = get_settings()
    store = Store(settings.database_path)
    with AIClient(settings, store) as client:
        try:
            result = client.json_response(
                name="email_draft",
                schema=DRAFT_SCHEMA,
                instructions="Write a short greeting draft. Do not send anything.",
                data={"recipient": "test@example.com", "instruction": "Say hello in one sentence."},
                max_output_tokens=200,
            )
        except httpx.HTTPStatusError as exc:
            error = exc.response.json().get("error") or {}
            print("OpenAI status:", exc.response.status_code)
            print("Error type:", error.get("type"))
            print("Error code:", error.get("code"))
            return
    print("Structured response received:", bool(result.get("subject") and result.get("body")))


if __name__ == "__main__":
    main()
