import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Entitlement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "entitlements"

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    edition: Mapped[str] = mapped_column(String(50), nullable=False, default="pro")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    max_devices: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    activation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signed_package: Mapped[str | None] = mapped_column(Text, nullable=True)
    package_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    public_key_version: Mapped[str] = mapped_column(String(30), nullable=False, default="v2")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    legacy_license_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("licenses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    customer = relationship("Customer")
    school = relationship("School")
    legacy_license = relationship("License")

    features = relationship(
        "EntitlementFeature",
        back_populates="entitlement",
        cascade="all, delete-orphan",
    )
    devices = relationship(
        "EntitlementDevice",
        back_populates="entitlement",
        cascade="all, delete-orphan",
    )
    renewals = relationship(
        "EntitlementRenewal",
        back_populates="entitlement",
        cascade="all, delete-orphan",
    )
    activations = relationship(
        "Activation",
        back_populates="entitlement",
    )
