from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.controllers.auth import router as auth_router
from app.controllers.agent import router as agent_router
from app.controllers.environments import router as environments_router
from app.core.config import get_settings
from app.core.database import create_database_schema


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        create_database_schema()
    yield


app = FastAPI(
    title="Cloud Control API",
    version="0.1.0",
    description="API central de controle de ambientes Cloud Control.",
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(environments_router)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
