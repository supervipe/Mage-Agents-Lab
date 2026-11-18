from collections.abc import AsyncIterator
from typing import Any

from app.agent.state import AgentState
from app.llm.client import FakeLLMClient
from app.tools.registry import ToolRegistry


class AgentLoop:
    def __init__(
        self,
        llm: FakeLLMClient,
        tools: ToolRegistry,
        max_steps: int = 5,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps

    async def run(self, user_message: str, state: AgentState) -> str:
        final_answer: str | None = None

        async for event in self.run_events(user_message=user_message, state=state):
            if event["type"] == "message":
                final_answer = event["content"]

        if final_answer is None:
            raise RuntimeError("Agent loop finished without a final response")

        return final_answer

    async def run_events(
        self,
        user_message: str,
        state: AgentState,
    ) -> AsyncIterator[dict[str, Any]]:
        state.add_user_message(user_message)

        for _ in range(self.max_steps):
            response = await self.llm.complete(
                messages=state.messages,
                tools=self.tools.get_openai_tool_schemas(),
            )

            if response.type == "message":
                if response.content is None:
                    raise ValueError("LLM returned a message without content")

                state.add_assistant_message(response.content)
                yield {
                    "type": "message",
                    "content": response.content,
                }
                yield {"type": "done"}
                return

            if response.type == "tool_call":
                if response.tool_call is None:
                    raise ValueError("LLM returned a tool_call response without a tool call")

                tool_call = response.tool_call
                yield {
                    "type": "tool_call",
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                }

                result = self.tools.run(tool_call.name, tool_call.arguments)

                state.add_tool_message(
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    content=str(result),
                )
                yield {
                    "type": "tool_result",
                    "id": tool_call.id,
                    "name": tool_call.name,
                    "content": str(result),
                }
                continue

            raise ValueError(f"Unknown LLM response type: {response.type}")

        raise RuntimeError("Agent loop reached max steps without a final response")
