from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    entitlement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entitlements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    license_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("licenses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    invoice_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    amount: Mapped[float] = mapped_column(
        Numeric(12,2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="NGN",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        index=True,
    )

    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    license = relationship("License", back_populates="invoices",)
    entitlement = relationship("Entitlement")
    school = relationship("School", back_populates="invoices",)
    payments = relationship(
        "Payment",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    receipts = relationship(
        "Receipt",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )