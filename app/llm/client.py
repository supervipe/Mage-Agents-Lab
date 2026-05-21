from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    type: Literal["tool_call", "message"]
    content: str | None = None
    tool_call: LLMToolCall | None = None


class FakeLLMClient:
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        has_tool_result = any(message["role"] == "tool" for message in messages)
        if has_tool_result:
            return LLMResponse(
                type="message",
                content="I found fake search results and used them to answer your question.",
            )
        else:
            return LLMResponse(
                type="tool_call",
                tool_call=LLMToolCall(
                    id="call_1",
                    name="web_search",
                    arguments={"query": "latest FastAPI news"},
                ),
            )
