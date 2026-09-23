import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.init_db import init_db
from app.routers import accounts as accounts_router
from app.routers import auth as auth_router
from app.routers import backup as backup_router
from app.routers import categories as categories_router
from app.routers import dashboard as dashboard_router
from app.routers import health as health_router
from app.routers import imports as imports_router
from app.routers import reports as reports_router
from app.routers import setup as setup_router
from app.routers import tags as tags_router
from app.routers import transactions as transactions_router
from app.routers import users as users_router
from app.security.deps import get_current_user
from app.tasks.backup_scheduler import backup_scheduler_loop


def _ensure_data_directories() -> None:
    data_root = Path(settings.data_dir)
    for subdirectory in ("database", "uploads", "reports", "backups"):
        (data_root / subdirectory).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    _ensure_data_directories()
    init_db()
    stop = asyncio.Event()
    scheduler_task: asyncio.Task[None] | None = None
    if settings.backup_scheduler_enabled:
        scheduler_task = asyncio.create_task(backup_scheduler_loop(stop))
    try:
        yield
    finally:
        stop.set()
        if scheduler_task is not None:
            await scheduler_task


def create_app() -> FastAPI:
    _ensure_data_directories()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    protected = [Depends(get_current_user)]
    application.include_router(health_router.router, prefix="/api")
    application.include_router(setup_router.router, prefix="/api/v1")
    application.include_router(auth_router.router, prefix="/api/v1")
    application.include_router(users_router.router, prefix="/api/v1")
    application.include_router(imports_router.router, prefix="/api/v1", dependencies=protected)
    application.include_router(dashboard_router.router, prefix="/api/v1", dependencies=protected)
    application.include_router(backup_router.router, prefix="/api/v1", dependencies=protected)
    application.include_router(transactions_router.router, prefix="/api", dependencies=protected)
    application.include_router(reports_router.router, prefix="/api", dependencies=protected)
    application.include_router(accounts_router.router, prefix="/api/v1", dependencies=protected)
    application.include_router(categories_router.router, prefix="/api/v1", dependencies=protected)
    application.include_router(tags_router.router, prefix="/api/v1", dependencies=protected)
    application.add_api_route(
        "/health",
        health_router.health,
        methods=["GET"],
        tags=["health"],
        include_in_schema=False,
    )
    return application


app = create_app()
