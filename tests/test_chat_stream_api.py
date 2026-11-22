import json

def test_chat_stream_endpoint_returns_agent_events(signed_in_client) -> None:
    with signed_in_client.stream(
        "POST",
        "/chat/stream",
        json={"message": "What is new with FastAPI?"},
    ) as response:
        assert response.status_code == 200
        body = response.read().decode()

    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    assert [event["type"] for event in events] == [
        "tool_call",
        "tool_result",
        "message",
        "done",
    ]
    assert events[0]["name"] == "web_search"
    assert events[2]["content"] == (
        "I found fake search results and used them to answer your question."
    )
