from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activation import Activation
from app.repositories.activation_repository import (
    activation_statistics,
    count_active_activations,
    create_activation_record,
    deactivate_activation,
    get_activation_by_id,
    get_activation_for_machine,
    upsert_license_device,
)
from app.repositories.license_repository import get_license_by_id, persist_license
from app.schemas.activation import ActivationRequest, ActivationTokenRequest, LicenseValidationResponse
from app.services.audit_service import record_audit_event
from app.services.license_service import is_activation_allowed, verify_signed_license


def validate_license_for_machine(db: Session, license_id: UUID, machine_id: str) -> LicenseValidationResponse:
    license_obj = get_license_by_id(db, license_id)
    if license_obj is None or license_obj.deleted_at is not None:
        return LicenseValidationResponse(valid=False, status="not_found", message="License not found", renewal_required=True)

    if license_obj.status in {"revoked", "suspended"}:
        return LicenseValidationResponse(
            valid=False,
            status=license_obj.status,
            message=f"License is {license_obj.status}.",
            renewal_required=True,
        )

    if license_obj.status != "active":
        return LicenseValidationResponse(valid=False, status=license_obj.status, message=f"License is {license_obj.status}.")

    if license_obj.expiry_at is not None and license_obj.expiry_at < datetime.now(timezone.utc):
        license_obj.status = "expired"
        persist_license(db, license_obj)
        db.commit()
        return LicenseValidationResponse(
            valid=False,
            status="expired",
            message="License has expired.",
            expires_at=license_obj.expiry_at,
            renewal_required=True,
        )

    verification = verify_signed_license(license_obj.signed_license)
    if not verification.valid:
        return LicenseValidationResponse(
            valid=False,
            status="verification_failed",
            message=verification.error or "License verification failed.",
        )

    if verification.payload and verification.payload.machine != machine_id:
        return LicenseValidationResponse(valid=False, status="fingerprint_mismatch", message="Machine fingerprint mismatch.")

    existing_activation = get_activation_for_machine(db, license_id, machine_id)
    if existing_activation is not None:
        return LicenseValidationResponse(
            valid=True,
            status="already_activated",
            message="License already activated on this machine.",
            renewal_required=False,
            license_id=license_obj.id,
            school_id=license_obj.school_id,
            remaining_activations=max(license_obj.max_activations - license_obj.activation_count, 0),
        )

    current_activation_count = count_active_activations(db, license_id)
    if not is_activation_allowed(current_activation_count, license_obj.max_activations):
        return LicenseValidationResponse(valid=False, status="limit_reached", message="Activation limit reached.", renewal_required=True)

    return LicenseValidationResponse(
        valid=True,
        status="valid",
        message="License is valid for activation.",
        renewal_required=False,
        license_id=license_obj.id,
        school_id=license_obj.school_id,
        remaining_activations=max(license_obj.max_activations - current_activation_count, 0),
    )


def activate_license(db: Session, license_id: UUID, payload: ActivationRequest) -> Activation:
    validation = validate_license_for_machine(db, license_id, payload.machine_id)
    if not validation.valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=validation.message)

    license_obj = get_license_by_id(db, license_id)
    if license_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")

    existing_activation = get_activation_for_machine(db, license_id, payload.machine_id)
    if existing_activation is not None:
        return existing_activation

    device = upsert_license_device(
        db,
        license_id=license_obj.id,
        device_id=None,
        machine_id=payload.machine_id,
        computer_name=payload.computer_name,
        windows_version=payload.windows_version,
        cpu_id=payload.cpu_id,
        motherboard_serial=payload.motherboard_serial,
        disk_serial=payload.disk_serial,
        mac_address=payload.mac_address,
        ip_address=payload.ip_address,
        last_user=payload.last_user,
    )
    if device.blacklisted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This device has been blacklisted.")

    activation = create_activation_record(
        db,
        license_id=license_id,
        device_id=device.id,
        school_id=license_obj.school_id,
        machine_id=payload.machine_id,
        computer_name=payload.computer_name,
        ip_address=payload.ip_address,
    )
    license_obj.activation_count += 1
    license_obj.last_activation_at = datetime.now(timezone.utc)
    persist_license(db, license_obj)
    record_audit_event(
        db,
        action="license_activated",
        entity_type="license",
        entity_id=str(license_obj.id),
        description=f"Activated on {payload.machine_id}",
    )
    db.commit()
    db.refresh(activation)
    return activation


def get_activation(db: Session, activation_id: UUID) -> Activation:
    activation = get_activation_by_id(db, activation_id)
    if activation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activation not found")
    return activation


def deactivate_license_activation(db: Session, activation_id: UUID) -> Activation:
    activation = get_activation(db, activation_id)
    deactivate_activation(db, activation)
    record_audit_event(
        db,
        action="license_deactivated",
        entity_type="license",
        entity_id=str(activation.license_id),
        description=f"Deactivated activation {activation.id}",
    )
    db.commit()
    db.refresh(activation)
    return activation


def get_activation_statistics(db: Session):
    return activation_statistics(db)


def validate_public_license(
    db: Session,
    *,
    license_key: str,
    machine_id: str,
    fingerprint: str,
):
    try:
        license_id = UUID(license_key)
    except ValueError:
        return {"valid": False, "status": "invalid", "expires_at": None, "message": "Invalid license key."}

    # Compatibility adapter: a legacy license key may now resolve to the
    # canonical Pro entitlement. Core functionality is never represented here.
    from app.models.entitlement import Entitlement
    from app.services.entitlement_service import EntitlementService

    entitlement = db.scalar(
        select(Entitlement).where(Entitlement.legacy_license_id == license_id)
    )
    if entitlement is not None:
        service = EntitlementService(db)
        status_value = service.refresh_status(entitlement)
        if status_value != "active":
            return {
                "valid": False,
                "status": status_value,
                "expires_at": entitlement.expires_at.isoformat() if entitlement.expires_at else None,
                "message": f"Pro entitlement is {status_value}.",
            }

        requested_machine = (machine_id or fingerprint).strip()
        if requested_machine:
            from app.models.entitlement_device import EntitlementDevice
            from app.models.license_device import LicenseDevice
            binding = db.scalar(
                select(EntitlementDevice)
                .join(LicenseDevice, LicenseDevice.id == EntitlementDevice.device_id)
                .where(
                    EntitlementDevice.entitlement_id == entitlement.id,
                    EntitlementDevice.status == "active",
                    LicenseDevice.machine_id == requested_machine,
                )
            )
            if binding is None:
                return {
                    "valid": False,
                    "status": "fingerprint_mismatch",
                    "expires_at": entitlement.expires_at.isoformat() if entitlement.expires_at else None,
                    "message": "Machine is not bound to this Pro entitlement.",
                }

        return {
            "valid": True,
            "status": "valid",
            "expires_at": entitlement.expires_at.isoformat() if entitlement.expires_at else None,
            "message": "Pro entitlement is valid for this machine.",
        }

    result = validate_license_for_machine(db, license_id, machine_id or fingerprint)
    return {
        "valid": result.valid,
        "status": result.status,
        "expires_at": result.expires_at.isoformat() if result.expires_at else None,
        "message": result.message,
    }


def activate_from_token(
    db: Session,
    payload: ActivationTokenRequest,
    *,
    verify_only: bool = False,
):
    from app.services.public_activation_service import complete_activation_from_token

    if verify_only:
        return {"valid": True, "message": "Activation token format accepted."}
    return complete_activation_from_token(db, payload)


def create_activation(
    db: Session,
    *,
    license_id: UUID,
    device_id: UUID,
    school_id: UUID,
    machine_id: str,
    computer_name: str | None = None,
    ip_address: str | None = None,
) -> Activation:
    return create_activation_record(
        db,
        license_id=license_id,
        device_id=device_id,
        school_id=school_id,
        machine_id=machine_id,
        computer_name=computer_name,
        ip_address=ip_address,
    )
