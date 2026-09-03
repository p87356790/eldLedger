from sqlalchemy import text

from app.database import engine
from app.schemas.health import HealthResponse, HelloResponse


def get_health() -> HealthResponse:
    database_status = "disconnected"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:
        database_status = "disconnected"

    overall = "ok" if database_status == "connected" else "degraded"
    return HealthResponse(
        status=overall,
        service="eldledger-backend",
        database=database_status,
    )


def get_hello() -> HelloResponse:
    return HelloResponse(message="Hello World", app="eldLedger")
