from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import CategoryDefaultScope, IntPKMixin, TimestampMixin, TransactionType


class Category(IntPKMixin, TimestampMixin, Base):
    """User-facing 분류. Maps to a postable income/expense account for auto-journal."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("organization_id", "owner_user_id", "name"),)

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
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, native_enum=False, length=32),
        nullable=False,
    )
    default_scope: Mapped[CategoryDefaultScope] = mapped_column(
        Enum(CategoryDefaultScope, native_enum=False, length=32),
        default=CategoryDefaultScope.COMMON,
        nullable=False,
    )
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="categories")
    owner: Mapped["User | None"] = relationship("User", foreign_keys=[owner_user_id])
    account: Mapped["Account"] = relationship("Account", back_populates="categories")
    parent: Mapped["Category | None"] = relationship(
        "Category",
        remote_side="Category.id",
        foreign_keys=[parent_id],
        back_populates="children",
    )
    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        foreign_keys=[parent_id],
        order_by="Category.sort_order",
    )
    items: Mapped[list["TransactionItem"]] = relationship("TransactionItem", back_populates="category")

    @property
    def chart_code(self) -> str | None:
        account = self.__dict__.get("account")
        if account is None:
            return None
        return account.code

    @property
    def chart_name(self) -> str | None:
        account = self.__dict__.get("account")
        if account is None:
            return None
        return account.name
