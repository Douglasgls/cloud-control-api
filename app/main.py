import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.client import router as client_router
from app.controllers.auth import router as auth_router
from app.controllers.agent import router as agent_router
from app.controllers.environments import router as environments_router
from app.realtime.websocket import router as realtime_router
from app.core.config import get_settings
from app.db.database import create_database_schema, SessionLocal
from app.services.connection_cleanup_service import ConnectionCleanupService

logger = logging.getLogger(__name__)


async def _background_connection_cleanup_loop(interval_seconds: int = 180):
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            with SessionLocal() as db:
                ConnectionCleanupService(db).cleanup_expired_pending_connections()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in background connection cleanup loop: %s", e)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        create_database_schema()

    try:
        with SessionLocal() as db:
            count = ConnectionCleanupService(db).cleanup_expired_pending_connections()
            logger.info("Startup connection cleanup completed (%d records expired).", count)
    except Exception as e:
        logger.error("Failed to run startup connection cleanup: %s", e)

    cleanup_task = asyncio.create_task(_background_connection_cleanup_loop(interval_seconds=180))

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Cloud Control API",
    version="0.1.0",
    description="API central de controle de ambientes Cloud Control.",
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(environments_router)
app.include_router(realtime_router)
app.include_router(client_router)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
