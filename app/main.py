import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.client import router as client_router
from app.api.network import router as network_router
from app.controllers.auth import router as auth_router
from app.controllers.agent import router as agent_router
from app.controllers.environments import router as environments_router
from app.realtime.websocket import router as realtime_router
from app.core.config import get_settings
from app.db.database import create_database_schema, SessionLocal
from app.realtime.websocket import connection_manager
from app.services.connection_cleanup_service import ConnectionCleanupService
from app.services.headscale.headscale_state_sync_service import HeadscaleStateSyncService

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


async def _background_headscale_sync_loop(interval_seconds: int = 30):
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            with SessionLocal() as db:
                sync_service = HeadscaleStateSyncService(db, connection_manager=connection_manager)
                await sync_service.sync()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in background Headscale state sync loop: %s", e)


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
    sync_task = asyncio.create_task(_background_headscale_sync_loop(interval_seconds=settings.headscale_sync_interval))

    yield

    cleanup_task.cancel()
    sync_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    try:
        await sync_task
    except asyncio.CancelledError:
        pass



from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Cloud Control API",
    version="0.1.0",
    description="API central de controle de ambientes Cloud Control.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(environments_router, prefix="/api")
app.include_router(realtime_router, prefix="/api")
app.include_router(client_router, prefix="/api")
app.include_router(network_router, prefix="/api")


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok", "message": "Deploy automático testado com sucesso!"}
