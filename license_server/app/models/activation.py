from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Activation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "activations"

    entitlement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entitlements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    installation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    activation_type: Mapped[str] = mapped_column(String(40), nullable=False, default="initial")

    license_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("licenses.id", ondelete="RESTRICT"), nullable=False, index=True, unique=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("license_devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    machine_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True, unique=True)
    computer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)

    license = relationship("License", back_populates="activations")
    device = relationship(
        "LicenseDevice",
        back_populates="activations",
    )
    school = relationship("School", back_populates="activations")
    entitlement = relationship("Entitlement", back_populates="activations")
