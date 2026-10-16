from datetime import date

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import BillStatus, IntPKMixin, TimestampMixin


class CardStatement(IntPKMixin, TimestampMixin, Base):
    """One month of card spending, paid from the linked bank the following month."""

    __tablename__ = "card_statements"
    __table_args__ = (
        CheckConstraint("amount > 0", name="card_statement_amount_positive"),
        UniqueConstraint(
            "created_by_user_id",
            "card_account_id",
            "period_start",
            name="uq_card_statement_user_card_period",
        ),
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bank_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    pay_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[BillStatus] = mapped_column(
        Enum(BillStatus, native_enum=False, length=32),
        default=BillStatus.OPEN,
        nullable=False,
        index=True,
    )
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="card_statements")
    card_account: Mapped["Account"] = relationship("Account", foreign_keys=[card_account_id])
    bank_account: Mapped["Account | None"] = relationship("Account", foreign_keys=[bank_account_id])
    transaction: Mapped["Transaction | None"] = relationship("Transaction")
