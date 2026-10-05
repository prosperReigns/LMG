import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class EntitlementRenewal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "entitlement_renewals"

    entitlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entitlements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    renewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    plan_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="NGN")
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    old_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    new_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    renewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    entitlement = relationship("Entitlement", back_populates="renewals")
    payment = relationship("Payment")
    admin = relationship("Admin")
