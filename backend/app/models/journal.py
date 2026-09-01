from datetime import date

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Text,
    event,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.models.base import Base
from app.models.enums import IntPKMixin, RecordStatus, TimestampMixin
from app.services.journal_balance import assert_journal_balanced, collect_line_amounts


class JournalEntry(IntPKMixin, TimestampMixin, Base):
    """Accounting journal document. Separate from the user Transaction."""

    __tablename__ = "journal_entries"

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus, native_enum=False, length=32),
        default=RecordStatus.DRAFT,
        nullable=False,
    )
    reverses_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="journal_entries")
    transaction: Mapped["Transaction | None"] = relationship("Transaction", back_populates="journal_entries")
    reverses_entry: Mapped["JournalEntry | None"] = relationship(
        "JournalEntry",
        remote_side="JournalEntry.id",
        foreign_keys=[reverses_entry_id],
    )
    lines: Mapped[list["JournalLine"]] = relationship(
        "JournalLine",
        back_populates="journal_entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.line_no",
    )

    def assert_balanced(self) -> None:
        assert_journal_balanced(collect_line_amounts(self.lines))


class JournalLine(IntPKMixin, TimestampMixin, Base):
    """Single debit or credit posting. Amounts are integer KRW."""

    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("debit_amount >= 0", name="debit_nonnegative"),
        CheckConstraint("credit_amount >= 0", name="credit_nonnegative"),
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="debit_xor_credit",
        ),
    )

    journal_entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transaction_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("transaction_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    debit_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    credit_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    journal_entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    account: Mapped["Account"] = relationship("Account", back_populates="journal_lines")
    transaction_item: Mapped["TransactionItem | None"] = relationship(
        "TransactionItem",
        back_populates="journal_lines",
    )


@event.listens_for(Session, "before_flush")
def _reject_unbalanced_journals(
    session: Session,
    flush_context: object,
    instances: object | None,
) -> None:
    entries: set[JournalEntry] = set()
    for obj in session.new.union(session.dirty):
        if isinstance(obj, JournalEntry):
            entries.add(obj)
        elif isinstance(obj, JournalLine) and obj.journal_entry is not None:
            entries.add(obj.journal_entry)
    for entry in entries:
        entry.assert_balanced()
