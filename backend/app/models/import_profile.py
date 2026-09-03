from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import CsvAmountMode, IntPKMixin, TimestampMixin


class ImportProfile(IntPKMixin, TimestampMixin, Base):
    """CSV column mapping for one ledger (organization)."""

    __tablename__ = "import_profiles"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    preset_key: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    date_column: Mapped[str] = mapped_column(String(64), nullable=False)
    merchant_column: Mapped[str] = mapped_column(String(64), nullable=False)
    memo_column: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_column: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outflow_column: Mapped[str | None] = mapped_column(String(64), nullable=True)
    inflow_column: Mapped[str | None] = mapped_column(String(64), nullable=True)
    type_column: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_mode: Mapped[CsvAmountMode] = mapped_column(
        Enum(CsvAmountMode, native_enum=False, length=32),
        default=CsvAmountMode.SIGNED,
        nullable=False,
    )
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="import_profiles")
