import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.responses import StreamingResponse

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


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    state = AgentState()
    agent = build_agent()

    async def event_stream():
        async for event in agent.run_events(
            user_message=request.message,
            state=state,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )
