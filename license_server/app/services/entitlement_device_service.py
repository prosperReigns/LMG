from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entitlement import Entitlement
from app.models.entitlement_device import EntitlementDevice
from app.models.license_device import LicenseDevice
from app.services.entitlement_service import EntitlementError


class EntitlementDeviceService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_device(
        self,
        *,
        machine_id: str,
        license_id: UUID | None = None,
        computer_name: str | None = None,
        ip_address: str | None = None,
    ) -> LicenseDevice:
        device = self.db.scalar(
            select(LicenseDevice).where(LicenseDevice.machine_id == machine_id)
        )
        if device is None:
            if license_id is None:
                raise EntitlementError("A new device requires the legacy license owner during migration")
            device = LicenseDevice(
                license_id=license_id,
                machine_id=machine_id,
                computer_name=computer_name,
                ip_address=ip_address,
            )
            self.db.add(device)
            self.db.flush()
        else:
            if computer_name:
                device.computer_name = computer_name
            if ip_address:
                device.ip_address = ip_address
            self.db.flush()
        return device

    def bind(
        self,
        entitlement: Entitlement,
        device: LicenseDevice,
    ) -> EntitlementDevice:
        existing = self.db.scalar(
            select(EntitlementDevice).where(
                EntitlementDevice.entitlement_id == entitlement.id,
                EntitlementDevice.device_id == device.id,
            )
        )
        if existing is not None:
            existing.status = "active"
            existing.deactivated_at = None
            self.db.flush()
            return existing

        active_count = self.db.scalar(
            select(EntitlementDevice).where(
                EntitlementDevice.entitlement_id == entitlement.id,
                EntitlementDevice.status == "active",
            ).with_only_columns(EntitlementDevice.id)
        )
        # Count explicitly to avoid relying on activation_count, which is historical.
        from sqlalchemy import func
        active_count = self.db.scalar(
            select(func.count(EntitlementDevice.id)).where(
                EntitlementDevice.entitlement_id == entitlement.id,
                EntitlementDevice.status == "active",
            )
        ) or 0

        if active_count >= entitlement.max_devices:
            raise EntitlementError("Entitlement device limit reached")

        binding = EntitlementDevice(
            entitlement_id=entitlement.id,
            device_id=device.id,
            status="active",
        )
        entitlement.activation_count += 1
        self.db.add(binding)
        self.db.flush()
        return binding

    def unbind(self, entitlement_device: EntitlementDevice) -> EntitlementDevice:
        entitlement_device.status = "inactive"
        from datetime import datetime, timezone
        entitlement_device.deactivated_at = datetime.now(timezone.utc)
        self.db.flush()
        return entitlement_device
