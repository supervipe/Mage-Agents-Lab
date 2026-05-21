from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.agent.loop import AgentLoop
from app.agent.state import AgentState
from app.llm.client import FakeLLMClient
from app.tools.registry import ToolRegistry
from app.tools.web_search import web_search_tool


router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    messages: list[dict[str, Any]]


def build_agent() -> AgentLoop:
    tools = ToolRegistry()
    tools.register(web_search_tool)
    return AgentLoop(
        llm=FakeLLMClient(),
        tools=tools,
    )


@router.post("")
async def chat(request: ChatRequest) -> ChatResponse:
    state = AgentState()
    agent = build_agent()

    answer = await agent.run(
        user_message=request.message,
        state=state,
    )

    return ChatResponse(
        answer=answer,
        messages=state.messages,
    )
