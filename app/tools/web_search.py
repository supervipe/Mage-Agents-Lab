from app.tools.base import Tool


def web_search(query: str) -> str:
    return f"Fake search results for: {query}"


web_search_tool = Tool(
    name="web_search",
    description="Search the web for recent or external information.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to run.",
            }
        },
        "required": ["query"],
    },
    handler=web_search,
)
