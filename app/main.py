import os

from fastapi import FastAPI

from app.auth import AuthMiddleware, router as auth_router
from app.api.chat import router as chat_router
from app.api.dashboard import router as dashboard_router
from starlette.middleware.trustedhost import TrustedHostMiddleware


app = FastAPI(title="Goblin Agents Lab")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[
    "127.0.0.1", "localhost", "testserver",
    *[value for value in (os.getenv("MESHNET_HOST"), os.getenv("MESHNET_BIND_IP")) if value],
])
app.add_middleware(AuthMiddleware)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
