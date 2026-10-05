from uuid import UUID
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.license_device import LicenseDevice
from app.models.entitlement_device import EntitlementDevice
from app.models.entitlement import Entitlement
from app.repositories.license_device_repository import (
    blacklist_device,
    get_device,
    list_devices,
    record_heartbeat,
    rename_device,
    unblacklist_device,
    update_device_notes,
    device_statistics,
    get_device_by_machine_id,
    create_device,
)
from app.services.audit_service import record_audit_event
from app.repositories.activation_repository import reset_device_activation
from app.repositories.license_repository import get_license_by_id

def get_devices(
    db: Session,
    *,
    search: str | None = None,
    status_filter: str | None = None,
    license_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
):
    offset = (page - 1) * page_size

    return list_devices(
        db,
        search=search,
        status=status_filter,
        license_id=license_id,
        offset=offset,
        limit=page_size,
    )

def get_device_or_404(
    db: Session,
    device_id: UUID,
) -> LicenseDevice:

    device = get_device(db, device_id)

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    return device

def rename_license_device(
    db: Session,
    device_id: UUID,
    new_name: str,
    *,
    admin=None,
    request=None,
):

    device = get_device_or_404(db, device_id)

    new_name = new_name.strip()

    if not new_name:
        raise HTTPException(
            status_code=400,
            detail="Device name cannot be empty.",
        )

    rename_device(
        db,
        device,
        new_name,
    )

    db.commit()
    db.refresh(device)

    record_audit_event(
        db,
        admin=admin,
        action="device_renamed",
        entity_type="device",
        entity_id=str(device.id),
        description=f"Renamed device to '{new_name}'",
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )

    db.commit()

    return device

def blacklist_license_device(
    db: Session,
    device_id: UUID,
    reason: str | None,
    *,
    admin=None,
    request=None,
):

    device = get_device_or_404(
        db,
        device_id,
    )

    if device.blacklisted:
        raise HTTPException(
            status_code=400,
            detail="Device is already blacklisted.",
        )

    blacklist_device(
        db,
        device,
        reason,
    )

    db.commit()
    db.refresh(device)

    record_audit_event(
        db,
        admin=admin,
        action="device_blacklisted",
        entity_type="device",
        entity_id=str(device.id),
        description=reason or "Device blacklisted",
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )

    db.commit()

    return device

def unblacklist_license_device(
    db: Session,
    device_id: UUID,
    *,
    admin=None,
    request=None,
):

    device = get_device_or_404(
        db,
        device_id,
    )

    if not device.blacklisted:
        raise HTTPException(
            status_code=400,
            detail="Device is not blacklisted.",
        )

    unblacklist_device(
        db,
        device,
    )

    db.commit()
    db.refresh(device)

    record_audit_event(
        db,
        admin=admin,
        action="device_unblacklisted",
        entity_type="device",
        entity_id=str(device.id),
        description="Removed device from blacklist",
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )

    db.commit()

    return device

def save_device_notes(
    db: Session,
    device_id: UUID,
    notes: str,
    *,
    admin=None,
    request=None,
):

    device = get_device_or_404(
        db,
        device_id,
    )

    update_device_notes(
        db,
        device,
        notes,
    )

    db.commit()
    db.refresh(device)

    record_audit_event(
        db,
        admin=admin,
        action="device_notes_updated",
        entity_type="device",
        entity_id=str(device.id),
        description="Updated internal device notes",
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )

    db.commit()

    return device

def update_device_heartbeat(
    db: Session,
    device_id: UUID,
    *,
    ip_address: str | None = None,
):

    device = get_device_or_404(
        db,
        device_id,
    )

    record_heartbeat(
        db,
        device,
        ip_address=ip_address,
    )

    db.commit()

    return device

def deactivate_device(
    db: Session,
    device_id: UUID,
    *,
    admin=None,
    request=None,
):

    device = get_device_or_404(
        db,
        device_id,
    )

    device.status = "inactive"

    db.add(device)

    db.commit()

    record_audit_event(
        db,
        admin=admin,
        action="device_deactivated",
        entity_type="device",
        entity_id=str(device.id),
        description="Device deactivated remotely.",
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )

    db.commit()

    return device

def reset_device(
    db: Session,
    device_id: UUID,
    *,
    admin=None,
    request=None,
):

    device = get_device_or_404(
        db,
        device_id,
    )

    reset_device_activation(
        db,
        device.id,
    )

    device.status = "active"

    db.add(device)

    record_audit_event(
        db,
        admin=admin,
        action="device_activation_reset",
        entity_type="device",
        entity_id=str(device.id),
        description="Activation reset remotely.",
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )

    db.commit()
    db.refresh(device)

    return device

def get_device_statistics(
    db: Session,
):

    return device_statistics(db)

def heartbeat_device(
    db: Session,
    payload,
):
    device = get_device_by_machine_id(
        db,
        payload.machine_id,
    )

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    if payload.last_user:
        device.last_user = payload.last_user

    updated = record_heartbeat(
        db,
        device,
        ip_address=payload.ip_address,
    )

    # ------------------------------------------------------------------
    # Find the canonical Pro entitlement first.
    entitlement_binding = db.scalar(
        select(EntitlementDevice).where(
            EntitlementDevice.device_id == device.id,
            EntitlementDevice.status == "active",
        )
    )
    if entitlement_binding is not None:
        entitlement = db.get(Entitlement, entitlement_binding.entitlement_id)
        if entitlement is not None:
            from app.services.entitlement_service import EntitlementService
            status_value = EntitlementService(db).refresh_status(entitlement)
            db.commit()
            return {
                "status": "alive" if status_value == "active" else status_value,
                "last_seen": updated.last_seen,
                "expiry_date": entitlement.expires_at.isoformat() if entitlement.expires_at else None,
                "grace_until": None,
                "message": f"Pro entitlement is {status_value}.",
            }

    # Fall back to the legacy license for old installations.
    license_obj = get_license_by_id(
        db,
        device.license_id,
    )

    if license_obj is None or license_obj.deleted_at is not None:
        db.commit()

        return {
            "status": "invalid",
            "last_seen": updated.last_seen,
            "expiry_date": None,
            "grace_until": None,
            "message": "License not found.",
        }

    # ------------------------------------------------------------------
    # Check license status
    # ------------------------------------------------------------------

    now = datetime.now(timezone.utc)

    if license_obj.status in {"revoked", "suspended"}:
        db.commit()

        return {
            "status": license_obj.status,
            "last_seen": updated.last_seen,
            "expiry_date": (
                license_obj.expiry_at.isoformat()
                if license_obj.expiry_at
                else None
            ),
            "grace_until": None,
            "message": f"License is {license_obj.status}.",
        }

    # ------------------------------------------------------------------
    # Check expiry
    # ------------------------------------------------------------------

    if (
        license_obj.expiry_at is not None
        and license_obj.expiry_at < now
    ):
        license_obj.status = "expired"

        db.add(license_obj)
        db.commit()

        return {
            "status": "expired",
            "last_seen": updated.last_seen,
            "expiry_date": license_obj.expiry_at.isoformat(),
            "grace_until": None,
            "message": "License has expired.",
        }

    # ------------------------------------------------------------------
    # Active license
    # ------------------------------------------------------------------

    db.commit()

    return {
        "status": "alive",
        "last_seen": updated.last_seen,
        "expiry_date": (
            license_obj.expiry_at.isoformat()
            if license_obj.expiry_at
            else None
        ),
        "grace_until": None,
        "message": "License is active.",
    }

def register_device(
    db: Session,
    *,
    license_id: UUID,
    machine_id: str,
    computer_name: str | None = None,
    ip_address: str | None = None,
    windows_version: str | None = None,
    cpu_id: str | None = None,
    motherboard_serial: str | None = None,
    disk_serial: str | None = None,
    mac_address: str | None = None,
    last_user: str | None = None,
) -> LicenseDevice:
    existing = get_device_by_machine_id(db, machine_id)
    if existing is not None:
        return existing

    device = create_device(
        db,
        license_id=license_id,
        machine_id=machine_id,
        computer_name=computer_name,
        ip_address=ip_address,
        windows_version=windows_version,
        cpu_id=cpu_id,
        motherboard_serial=motherboard_serial,
        disk_serial=disk_serial,
        mac_address=mac_address,
        last_user=last_user,
    )
    db.commit()
    db.refresh(device)
    return device
