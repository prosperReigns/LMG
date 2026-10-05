from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import Base


class ActivationToken(Base):
    __tablename__ = "activation_tokens"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    token: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )

    purchase_session_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_sessions.id"),
        nullable=False,
    )

    entitlement_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entitlements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    license_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("licenses.id"),
        nullable=False,
    )

    machine_fingerprint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    download_nonce: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
        nullable=True,
        index=True,
    )

    download_nonce_expires_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
    )

    download_nonce_used_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    purchase_session = relationship("PurchaseSession", foreign_keys="ActivationToken.purchase_session_id")

    license = relationship("License")
