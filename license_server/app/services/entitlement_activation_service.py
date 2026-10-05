from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activation import Activation
from app.models.entitlement import Entitlement
from app.models.entitlement_device import EntitlementDevice
from app.models.license_device import LicenseDevice
from app.repositories.activation_token_repository import get_by_token
from app.services.entitlement_device_service import EntitlementDeviceService
from app.services.entitlement_service import EntitlementError, EntitlementService
from app.services.activation_token_service import validate_token, consume_token
from app.utils.time import utcnow


def activate_from_token(
    db: Session,
    *,
    token: str,
    installation_id: str,
    machine_id: str,
    computer_name: str | None = None,
    app_version: str | None = None,
) -> Entitlement:
    activation_token = get_by_token(db, token)
    validate_token(activation_token)

    if activation_token.entitlement_id is None:
        raise EntitlementError("Activation token is not linked to a Pro entitlement")

    entitlement = db.get(Entitlement, activation_token.entitlement_id)
    if entitlement is None:
        raise EntitlementError("Pro entitlement not found")

    service = EntitlementService(db)
    if not service.is_active(entitlement):
        raise EntitlementError("Pro entitlement is not active")

    # Reuse an existing device when the machine is already known.
    device = db.scalar(
        select(LicenseDevice).where(LicenseDevice.machine_id == machine_id)
    )
    if device is None:
        device = EntitlementDeviceService(db).get_or_create_device(
            machine_id=machine_id,
            license_id=activation_token.license_id,
            computer_name=computer_name,
        )
    else:
        if device.blacklisted:
            raise EntitlementError("This device has been blacklisted")

    binding = EntitlementDeviceService(db).bind(entitlement, device)

    existing_activation = db.scalar(
        select(Activation).where(
            Activation.entitlement_id == entitlement.id,
            Activation.machine_id == machine_id,
            Activation.status == "active",
        )
    )
    if existing_activation is None:
        activation = Activation(
            license_id=activation_token.license_id,
            entitlement_id=entitlement.id,
            device_id=device.id,
            school_id=entitlement.school_id,
            machine_id=machine_id,
            computer_name=computer_name,
            activation_type="initial",
            status="active",
        )
        db.add(activation)

    package = service.issue_signed_package(
        entitlement,
        installation_id=installation_id,
        machine_id=machine_id,
    )
    consume_token(db, activation_token)
    db.commit()
    return entitlement
