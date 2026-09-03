from sqlalchemy.orm import Session

from app.models import AuditLog


class AuditService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        action: str,
        user_id: int | None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        details: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        self._session.add(entry)
        self._session.flush()
        return entry
