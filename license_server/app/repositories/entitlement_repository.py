from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entitlement import Entitlement


def get_entitlement(db: Session, entitlement_id: UUID) -> Entitlement | None:
    statement = (
        select(Entitlement)
        .options(
            selectinload(Entitlement.features),
            selectinload(Entitlement.devices),
        )
        .where(Entitlement.id == entitlement_id)
    )
    return db.scalar(statement)


def get_active_pro_entitlement(
    db: Session,
    *,
    product_code: str = "examcenter",
    customer_id: UUID | None = None,
    school_id: UUID | None = None,
) -> Entitlement | None:
    statement = (
        select(Entitlement)
        .options(selectinload(Entitlement.features), selectinload(Entitlement.devices))
        .where(
            Entitlement.product_code == product_code,
            Entitlement.edition == "pro",
            Entitlement.status == "active",
        )
        .order_by(Entitlement.expires_at.desc().nulls_last(), Entitlement.created_at.desc())
    )
    if customer_id is not None:
        statement = statement.where(Entitlement.customer_id == customer_id)
    if school_id is not None:
        statement = statement.where(Entitlement.school_id == school_id)
    return db.scalar(statement)


def persist_entitlement(db: Session, entitlement: Entitlement) -> Entitlement:
    db.add(entitlement)
    db.flush()
    return entitlement


def set_status(
    db: Session,
    entitlement: Entitlement,
    *,
    status: str,
    when: datetime | None = None,
) -> Entitlement:
    now = when or datetime.now(timezone.utc)
    entitlement.status = status
    if status == "revoked":
        entitlement.revoked_at = now
    elif status == "suspended":
        entitlement.suspended_at = now
    elif status == "active":
        entitlement.revoked_at = None
        entitlement.suspended_at = None
    db.add(entitlement)
    db.flush()
    return entitlement
