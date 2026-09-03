from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import AccountType, IntPKMixin, NormalBalance, PaymentInstrumentKind, TimestampMixin


class Account(IntPKMixin, TimestampMixin, Base):
    """Formal chart-of-accounts node. User wallets are postable payment methods."""

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    normal_balance: Mapped[NormalBalance] = mapped_column(
        Enum(NormalBalance, native_enum=False, length=16),
        nullable=False,
    )
    is_postable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_payment_method: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    instrument_kind: Mapped[PaymentInstrumentKind | None] = mapped_column(
        Enum(PaymentInstrumentKind, native_enum=False, length=32),
        nullable=True,
        index=True,
    )
    currency: Mapped[str] = mapped_column(String(3), default="KRW", nullable=False)
    opening_balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    institution: Mapped[str | None] = mapped_column(String(100), nullable=True)
    card_payment_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    settlement_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="accounts")
    owner: Mapped["User | None"] = relationship("User", foreign_keys=[owner_user_id])
    parent: Mapped["Account | None"] = relationship(
        "Account",
        remote_side="Account.id",
        foreign_keys=[parent_id],
        back_populates="children",
    )
    children: Mapped[list["Account"]] = relationship(
        "Account",
        back_populates="parent",
        foreign_keys=[parent_id],
    )
    settlement_account: Mapped["Account | None"] = relationship(
        "Account",
        remote_side="Account.id",
        foreign_keys=[settlement_account_id],
    )
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="account")
    journal_lines: Mapped[list["JournalLine"]] = relationship("JournalLine", back_populates="account")
