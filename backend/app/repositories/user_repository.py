from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import RefreshToken, User
from app.models.enums import UserRole


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def count(self) -> int:
        return int(self._session.scalar(select(func.count()).select_from(User)) or 0)

    def list_for_organization(self, organization_id: int) -> list[User]:
        return list(
            self._session.scalars(
                select(User).where(User.organization_id == organization_id).order_by(User.id)
            ).all()
        )

    def find_login(self, identifier: str) -> User | None:
        lowered = identifier.strip().lower()
        return self._session.scalar(
            select(User).where(or_(User.username == identifier.strip(), func.lower(User.email) == lowered))
        )

    def get_by_username(self, username: str) -> User | None:
        return self._session.scalar(select(User).where(User.username == username))

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(func.lower(User.email) == email.lower()))

    def admin_count(self, organization_id: int, *, exclude_id: int | None = None) -> int:
        stmt = select(func.count()).select_from(User).where(
            User.organization_id == organization_id,
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
        )
        if exclude_id is not None:
            stmt = stmt.where(User.id != exclude_id)
        return int(self._session.scalar(stmt) or 0)

    def get_refresh(self, jti: str) -> RefreshToken | None:
        return self._session.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
