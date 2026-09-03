from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

import jwt

from app.config import settings

ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(*, user_id: int, organization_id: int, role: str) -> str:
    expire = _now() + timedelta(minutes=settings.access_token_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org": organization_id,
        "role": role,
        "typ": "access",
        "exp": expire,
        "iat": _now(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(*, user_id: int) -> tuple[str, str, datetime]:
    jti = uuid4().hex
    expire = _now() + timedelta(days=settings.refresh_token_days)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": jti,
        "typ": "refresh",
        "exp": expire,
        "iat": _now(),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return token, jti, expire


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("token type mismatch")
    return payload
