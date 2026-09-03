from fastapi import APIRouter

from app.schemas.health import HealthResponse, HelloResponse
from app.services.health_service import get_health, get_hello

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return get_health()


@router.get("/hello", response_model=HelloResponse)
def hello() -> HelloResponse:
    return get_hello()
