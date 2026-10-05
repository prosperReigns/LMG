from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entitlement import Entitlement
from app.models.entitlement_feature import EntitlementFeature
from app.models.entitlement_device import EntitlementDevice
from app.models.license import License
from app.models.license_device import LicenseDevice
from app.services.entitlement_service import DEFAULT_PRO_FEATURES


class EntitlementMigrationService:
    """Convert an existing paid/trial License into the new Pro entitlement model."""

    def __init__(self, db: Session):
        self.db = db

    def migrate_license(self, license_obj: License) -> Entitlement:
        existing = self.db.query(Entitlement).filter(
            Entitlement.legacy_license_id == license_obj.id
        ).first()
        if existing is not None:
            return existing

        school = license_obj.school
        customer_id = school.customer_id if school is not None else None

        status = self._map_status(license_obj)
        starts_at = license_obj.issued_at
        expires_at = license_obj.expiry_at

        entitlement = Entitlement(
            customer_id=customer_id,
            school_id=license_obj.school_id,
            product_code="examcenter",
            edition="pro",
            status=status,
            starts_at=starts_at,
            expires_at=expires_at,
            max_devices=max(1, license_obj.max_activations),
            activation_count=0,
            signed_package=None,
            package_version=2,
            public_key_version="v2",
            legacy_license_id=license_obj.id,
        )
        self.db.add(entitlement)
        self.db.flush()

        # Preserve only the feature set explicitly represented by the legacy package.
        legacy_features = {}
        try:
            from app.utils.license_crypto import verify_license
            if license_obj.signed_license:
                result = verify_license(license_obj.signed_license)
                if result.valid and result.payload is not None:
                    legacy_features = result.payload.features or {}
        except Exception:
            legacy_features = {}

        # A legacy package with no explicit feature map receives only the root Pro entitlement.
        # Future Pro features must not be silently granted during migration.
        features = {"pro": True}\n        features.update(legacy_features)\n        for code, enabled in features.items():
            self.db.add(
                EntitlementFeature(
                    entitlement_id=entitlement.id,
                    feature_code=code,
                    enabled=bool(enabled),
                )
            )

        for device in license_obj.devices:
            self.db.add(
                EntitlementDevice(
                    entitlement_id=entitlement.id,
                    device_id=device.id,
                    status="active" if not device.blacklisted else "inactive",
                    last_verified_at=device.last_seen,
                )
            )
            entitlement.activation_count += 1

        self.db.flush()

        active_device = next(
            (device for device in license_obj.devices if not device.blacklisted),
            None,
        )
        machine_id = active_device.machine_id if active_device is not None else license_obj.machine_fingerprint
        try:
            from app.services.entitlement_service import EntitlementService
            EntitlementService(self.db).issue_signed_package(
                entitlement,
                installation_id=f"legacy-{license_obj.id}",
                machine_id=machine_id,
            )
        except Exception:
            entitlement.signed_package = None
            self.db.add(entitlement)

        self.db.flush()
        return entitlement

    def migrate_all(self):
        licenses = self.db.scalars(
            select(License).order_by(License.issued_at, License.id)
        ).all()
        result = {"total": len(licenses), "migrated": 0, "existing": 0}
        for license_obj in licenses:
            existing = self.db.scalar(
                select(Entitlement).where(
                    Entitlement.legacy_license_id == license_obj.id
                )
            )
            if existing is not None:
                result["existing"] += 1
                continue
            self.migrate_license(license_obj)
            self.db.commit()
            result["migrated"] += 1
        return result

    @staticmethod
    def _map_status(license_obj: License) -> str:
        now = datetime.now(timezone.utc)
        if license_obj.revoked_at is not None or license_obj.status == "revoked":
            return "revoked"
        if license_obj.suspended_at is not None or license_obj.status == "suspended":
            return "suspended"
        if license_obj.expiry_at is not None and license_obj.expiry_at <= now:
            return "expired"
        if license_obj.issued_at > now:
            return "pending"
        return "active"
