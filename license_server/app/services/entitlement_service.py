from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.entitlement import Entitlement
from app.models.entitlement_feature import EntitlementFeature
from app.repositories.entitlement_repository import (
    get_active_pro_entitlement,
    get_entitlement,
    persist_entitlement,
    set_status,
)

ENTITLEMENT_STATUSES = {"pending", "active", "expired", "suspended", "revoked", "cancelled"}

DEFAULT_PRO_FEATURES: dict[str, bool] = {
    "pro": True,
    "advanced_reports": True,
    "cloud_backup": True,
    "remote_results": True,
    "multi_campus": False,
    "disaster_recovery": True,
    "ai_features": True,
}


class EntitlementError(ValueError):
    """Raised when an entitlement operation is invalid."""


class EntitlementService:
    PRODUCT_CODE = "examcenter"
    EDITION = "pro"

    def __init__(self, db: Session):
        self.db = db

    def get(self, entitlement_id: UUID) -> Entitlement | None:
        return get_entitlement(self.db, entitlement_id)

    def create_pro_entitlement(
        self,
        *,
        customer_id: UUID | None,
        school_id: UUID | None,
        starts_at: datetime,
        expires_at: datetime | None,
        max_devices: int = 1,
        features: dict[str, bool] | None = None,
        legacy_license_id: UUID | None = None,
    ) -> Entitlement:
        if max_devices < 1:
            raise EntitlementError("max_devices must be at least 1")
        if expires_at is not None and expires_at <= starts_at:
            raise EntitlementError("expires_at must be after starts_at")

        entitlement = Entitlement(
            id=uuid4(),
            customer_id=customer_id,
            school_id=school_id,
            product_code=self.PRODUCT_CODE,
            edition=self.EDITION,
            status="active",
            starts_at=starts_at,
            expires_at=expires_at,
            max_devices=max_devices,
            activation_count=0,
            package_version=2,
            public_key_version="v2",
            legacy_license_id=legacy_license_id,
        )
        persist_entitlement(self.db, entitlement)

        feature_map = dict(DEFAULT_PRO_FEATURES)
        if features is not None:
            feature_map.update(features)

        for code, enabled in feature_map.items():
            self.db.add(
                EntitlementFeature(
                    entitlement_id=entitlement.id,
                    feature_code=code,
                    enabled=bool(enabled),
                )
            )
        self.db.flush()
        return entitlement

    def refresh_status(self, entitlement: Entitlement) -> str:
        now = datetime.now(timezone.utc)

        if entitlement.status in {"revoked", "cancelled"}:
            return entitlement.status

        if entitlement.status == "suspended":
            return "suspended"

        if entitlement.starts_at > now:
            return "pending"

        if entitlement.expires_at is not None and entitlement.expires_at <= now:
            if entitlement.status != "expired":
                entitlement.status = "expired"
                self.db.add(entitlement)
                self.db.flush()
            return "expired"

        if entitlement.status != "active":
            entitlement.status = "active"
            self.db.add(entitlement)
            self.db.flush()

        return "active"

    def is_active(self, entitlement: Entitlement | None) -> bool:
        if entitlement is None:
            return False
        return self.refresh_status(entitlement) == "active"

    def has_feature(self, entitlement: Entitlement | None, feature_code: str) -> bool:
        if not self.is_active(entitlement):
            return False
        if feature_code == "pro":
            return True

        return any(
            feature.feature_code == feature_code and feature.enabled
            for feature in entitlement.features
        )

    def can_use(
        self,
        *,
        feature_code: str,
        entitlement_id: UUID | None = None,
        customer_id: UUID | None = None,
        school_id: UUID | None = None,
    ) -> bool:
        entitlement = (
            self.get(entitlement_id)
            if entitlement_id is not None
            else get_active_pro_entitlement(
                self.db,
                product_code=self.PRODUCT_CODE,
                customer_id=customer_id,
                school_id=school_id,
            )
        )
        return self.has_feature(entitlement, feature_code)

    def suspend(self, entitlement: Entitlement) -> Entitlement:
        return set_status(self.db, entitlement, status="suspended")

    def revoke(self, entitlement: Entitlement) -> Entitlement:
        return set_status(self.db, entitlement, status="revoked")

    def reactivate(self, entitlement: Entitlement) -> Entitlement:
        if entitlement.status in {"revoked", "cancelled"}:
            raise EntitlementError("Revoked or cancelled entitlements cannot be reactivated")
        return set_status(self.db, entitlement, status="active")

    def get_feature_snapshot(self, entitlement: Entitlement) -> dict[str, bool]:
        snapshot: dict[str, bool] = {"pro": self.is_active(entitlement)}
        if entitlement is None:
            return snapshot
        for feature in entitlement.features:
            snapshot[feature.feature_code] = bool(feature.enabled and snapshot["pro"])
        return snapshot
