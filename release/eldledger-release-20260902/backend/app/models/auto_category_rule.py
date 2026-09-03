from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import IntPKMixin, Scope, TimestampMixin


class AutoCategoryRule(IntPKMixin, TimestampMixin, Base):
    """Merchant-keyword rule that suggests 분류 / 개인·사업 / tags."""

    __tablename__ = "auto_category_rules"

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    merchant_keyword: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    scope: Mapped[Scope] = mapped_column(
        Enum(Scope, native_enum=False, length=32),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="auto_category_rules")
    payment_account: Mapped["Account | None"] = relationship("Account", foreign_keys=[payment_account_id])
    category: Mapped["Category"] = relationship("Category")
    rule_tags: Mapped[list["AutoCategoryRuleTag"]] = relationship(
        "AutoCategoryRuleTag",
        back_populates="rule",
        cascade="all, delete-orphan",
    )

    @property
    def tags(self) -> list["Tag"]:
        return [link.tag for link in self.rule_tags if link.tag is not None]


class AutoCategoryRuleTag(Base):
    __tablename__ = "auto_category_rule_tags"
    __table_args__ = (UniqueConstraint("rule_id", "tag_id"),)

    rule_id: Mapped[int] = mapped_column(
        ForeignKey("auto_category_rules.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    rule: Mapped["AutoCategoryRule"] = relationship("AutoCategoryRule", back_populates="rule_tags")
    tag: Mapped["Tag"] = relationship("Tag")
