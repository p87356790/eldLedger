from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tag, TransactionTag


class TagRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, tag_id: int) -> Tag | None:
        return self._session.get(Tag, tag_id)

    def list_tags(self, organization_id: int) -> list[Tag]:
        return list(
            self._session.scalars(
                select(Tag).where(Tag.organization_id == organization_id).order_by(Tag.name)
            ).all()
        )

    def get_by_name(self, organization_id: int, name: str) -> Tag | None:
        return self._session.scalar(select(Tag).where(Tag.organization_id == organization_id, Tag.name == name))

    def used_in_transactions(self, tag_id: int) -> bool:
        return self._session.scalar(select(TransactionTag.tag_id).where(TransactionTag.tag_id == tag_id).limit(1)) is not None
