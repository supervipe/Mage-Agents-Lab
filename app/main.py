from fastapi import FastAPI

from app.api.chat import router as chat_router


app = FastAPI(title="Goblin Agents Lab")
app.include_router(chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
