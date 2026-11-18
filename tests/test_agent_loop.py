import pytest

from app.agent.loop import AgentLoop
from app.agent.state import AgentState
from app.llm.client import FakeLLMClient
from app.tools.registry import ToolRegistry
from app.tools.web_search import web_search_tool


@pytest.mark.asyncio
async def test_agent_loop_runs_tool_and_returns_final_answer() -> None:
    tools = ToolRegistry()
    tools.register(web_search_tool)

    state = AgentState()
    agent = AgentLoop(
        llm=FakeLLMClient(),
        tools=tools,
    )

    answer = await agent.run(
        user_message="What is new with FastAPI?",
        state=state,
    )

    assert answer == "I found fake search results and used them to answer your question."
    assert [message["role"] for message in state.messages] == [
        "user",
        "tool",
        "assistant",
    ]
    assert state.messages[1]["name"] == "web_search"
