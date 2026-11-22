def test_chat_endpoint_returns_answer_and_messages(signed_in_client) -> None:
    response = signed_in_client.post(
        "/chat",
        json={"message": "What is new with FastAPI?"},
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["answer"]
        == "I found fake search results and used them to answer your question."
    )
    assert [message["role"] for message in data["messages"]] == [
        "user",
        "tool",
        "assistant",
    ]
    assert data["messages"][1]["name"] == "web_search"
