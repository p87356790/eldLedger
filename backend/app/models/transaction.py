from datetime import date

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import IntPKMixin, RecordStatus, Scope, TimestampMixin, TransactionType


class Transaction(IntPKMixin, TimestampMixin, Base):
    """User-facing cashbook entry. Never stored as a journal line."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    scope: Mapped[Scope] = mapped_column(
        Enum(Scope, native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus, native_enum=False, length=32),
        default=RecordStatus.DRAFT,
        nullable=False,
    )
    payment_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transfer_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="transactions")
    created_by: Mapped["User | None"] = relationship("User", back_populates="transactions")
    payment_account: Mapped["Account"] = relationship("Account", foreign_keys=[payment_account_id])
    transfer_account: Mapped["Account | None"] = relationship("Account", foreign_keys=[transfer_account_id])
    items: Mapped[list["TransactionItem"]] = relationship(
        "TransactionItem",
        back_populates="transaction",
        cascade="all, delete-orphan",
        order_by="TransactionItem.line_no",
    )
    transaction_tags: Mapped[list["TransactionTag"]] = relationship(
        "TransactionTag",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
    journal_entries: Mapped[list["JournalEntry"]] = relationship("JournalEntry", back_populates="transaction")

    @property
    def tags(self) -> list["Tag"]:
        return [link.tag for link in self.transaction_tags if link.tag is not None]


class TransactionItem(IntPKMixin, TimestampMixin, Base):
    """Split line on a user transaction (including MIXED personal/business)."""

    __tablename__ = "transaction_items"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
    )

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scope: Mapped[Scope] = mapped_column(
        Enum(Scope, native_enum=False, length=32),
        nullable=False,
    )
    memo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    line_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="items")
    category: Mapped["Category | None"] = relationship("Category", back_populates="items")
    account: Mapped["Account | None"] = relationship("Account")
    journal_lines: Mapped[list["JournalLine"]] = relationship("JournalLine", back_populates="transaction_item")
