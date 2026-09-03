from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import JournalEntry
from app.models.enums import RecordStatus


class JournalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: JournalEntry) -> JournalEntry:
        self._session.add(entry)
        return entry

    def active_for_transaction(self, transaction_id: int) -> JournalEntry | None:
        return self._session.scalar(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(
                JournalEntry.transaction_id == transaction_id,
                JournalEntry.status == RecordStatus.CONFIRMED,
                JournalEntry.reverses_entry_id.is_(None),
            )
        )
