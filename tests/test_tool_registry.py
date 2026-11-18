import pytest

from app.tools.base import Tool
from app.tools.registry import ToolRegistry


def echo(text: str) -> str:
    return f"Echo: {text}"


def make_echo_tool() -> Tool:
    return Tool(
        name="echo",
        description="Echo text back.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
        handler=echo,
    )


def test_register_and_run_tool() -> None:
    registry = ToolRegistry()
    registry.register(make_echo_tool())

    result = registry.run("echo", {"text": "hello"})

    assert result == "Echo: hello"


def test_register_duplicate_tool_name_raises_error() -> None:
    registry = ToolRegistry()
    tool = make_echo_tool()
    registry.register(tool)

    with pytest.raises(ValueError):
        registry.register(tool)
