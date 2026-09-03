from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tag, TransactionTag


class TagRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, tag_id: int) -> Tag | None:
        return self._session.get(Tag, tag_id)

    def list_tags(self, organization_id: int, *, owner_user_id: int | None = None) -> list[Tag]:
        stmt = select(Tag).where(Tag.organization_id == organization_id).order_by(Tag.name)
        if owner_user_id is not None:
            stmt = stmt.where(Tag.owner_user_id == owner_user_id)
        return list(self._session.scalars(stmt).all())

    def get_by_name(self, organization_id: int, name: str, *, owner_user_id: int | None = None) -> Tag | None:
        stmt = select(Tag).where(Tag.organization_id == organization_id, Tag.name == name)
        if owner_user_id is not None:
            stmt = stmt.where(Tag.owner_user_id == owner_user_id)
        else:
            stmt = stmt.where(Tag.owner_user_id.is_(None))
        return self._session.scalar(stmt)

    def used_in_transactions(self, tag_id: int) -> bool:
        return self._session.scalar(select(TransactionTag.tag_id).where(TransactionTag.tag_id == tag_id).limit(1)) is not None
