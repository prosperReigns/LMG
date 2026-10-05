import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class LicenseDevice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "license_devices"

    license_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("licenses.id", ondelete="SET NULL"), nullable=True, index=True, unique=True)

    machine_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True, unique=True)

    computer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)

    activation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)

    windows_version: Mapped[str | None] = mapped_column(String(120),nullable=True,)

    cpu_id: Mapped[str | None] = mapped_column(String(255),nullable=True,)

    motherboard_serial: Mapped[str | None] = mapped_column(String(255),nullable=True,)

    disk_serial: Mapped[str | None] = mapped_column(String(255),nullable=True,)

    mac_address: Mapped[str | None] = mapped_column(String(100),nullable=True,)

    last_user: Mapped[str | None] = mapped_column(String(255),nullable=True,)

    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False,)
    
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False,)

    blacklisted: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False,)

    blacklist_reason: Mapped[str | None] = mapped_column(Text,nullable=True,)
    notes: Mapped[str | None] = mapped_column(Text,nullable=True,)

    renamed_to: Mapped[str | None] = mapped_column(String(255),nullable=True,)
    

    license = relationship("License", back_populates="devices",)
    activations = relationship(
    "Activation",
    back_populates="device",
)
