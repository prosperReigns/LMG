from datetime import datetime, timedelta, timezone
from uuid import UUID as PyUUID
from uuid import uuid4
import secrets

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def generate_poll_token() -> str:
    return secrets.token_urlsafe(32)


class PurchaseSession(Base):
    __tablename__ = "purchase_sessions"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    plan_code: Mapped[str] = mapped_column(String(50), nullable=False)
    edition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    installation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    machine_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="NGN")
    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    customer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    school_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    payment_reference: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    poll_token: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
        default=generate_poll_token,
    )
    checkout_token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    checkout_url: Mapped[str] = mapped_column(String(500), nullable=True)
    gateway: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gateway_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gateway_transaction_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    gateway_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    customer_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    school_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True)
    license_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("licenses.id"), nullable=True)
    entitlement_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("entitlements.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)
    payment_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True)
    device_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("license_devices.id"), nullable=True)
    activation_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("activations.id"), nullable=True)
    receipt_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("receipts.id"), nullable=True)
    activation_token_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("activation_tokens.id"), nullable=True)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=24),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
