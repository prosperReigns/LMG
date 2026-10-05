from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.entitlement import Entitlement
from app.models.entitlement_renewal import EntitlementRenewal
from app.services.entitlement_service import EntitlementError


class EntitlementRenewalService:
    def __init__(self, db: Session):
        self.db = db

    def renew(
        self,
        entitlement: Entitlement,
        *,
        duration_days: int,
        amount: Decimal | float = 0,
        currency: str = "NGN",
        payment_id: UUID | None = None,
        renewed_by: UUID | None = None,
        plan_code: str | None = None,
        notes: str | None = None,
    ) -> EntitlementRenewal:
        if duration_days <= 0:
            raise EntitlementError("duration_days must be greater than zero")
        if entitlement.status in {"revoked", "cancelled"}:
            raise EntitlementError("Revoked or cancelled entitlements cannot be renewed")

        now = datetime.now(timezone.utc)
        old_expiry = entitlement.expires_at

        if old_expiry is not None and old_expiry > now:
            base = old_expiry
        else:
            base = now

        new_expiry = base + timedelta(days=duration_days)
        entitlement.starts_at = min(entitlement.starts_at, now)
        entitlement.expires_at = new_expiry
        entitlement.status = "active"
        entitlement.revoked_at = None
        entitlement.suspended_at = None

        renewal = EntitlementRenewal(
            entitlement_id=entitlement.id,
            payment_id=payment_id,
            renewed_by=renewed_by,
            plan_code=plan_code,
            amount=amount,
            currency=currency,
            duration_days=duration_days,
            old_expiry=old_expiry,
            new_expiry=new_expiry,
            renewed_at=now,
            notes=notes,
        )
        self.db.add(renewal)
        self.db.flush()
        return renewal
