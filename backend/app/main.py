from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.init_db import init_db
from app.routers import health as health_router
from app.routers import reports as reports_router
from app.routers import transactions as transactions_router


def _ensure_data_directories() -> None:
    data_root = Path(settings.data_dir)
    for subdirectory in ("database", "uploads", "reports", "backups"):
        (data_root / subdirectory).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    _ensure_data_directories()
    init_db()
    yield


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
    application.include_router(health_router.router, prefix="/api")
    application.include_router(transactions_router.router, prefix="/api")
    application.include_router(reports_router.router, prefix="/api")
    application.add_api_route(
        "/health",
        health_router.health,
        methods=["GET"],
        tags=["health"],
        include_in_schema=False,
    )
    return application


app = create_app()
