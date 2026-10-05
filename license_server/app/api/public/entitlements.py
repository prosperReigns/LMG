from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.entitlement_api import (
    ProActivationRequest,
    ProActivationResponse,
    ProDeviceChangeRequest,
    ProFeatureCheckRequest,
    ProFeatureCheckResponse,
    ProHeartbeatRequest,
    ProHeartbeatResponse,
)
from app.services.entitlement_activation_service import activate_from_token
from app.services.entitlement_device_service import EntitlementDeviceService
from app.services.entitlement_service import EntitlementError, EntitlementService


router = APIRouter(
    prefix="/api/v2/public/entitlements",
    tags=["Pro Entitlements"],
)


@router.post("/activate", response_model=ProActivationResponse)
def activate_entitlement(
    payload: ProActivationRequest,
    db: Session = Depends(get_db),
):
    try:
        entitlement = activate_from_token(
            db,
            token=payload.activation_token,
            installation_id=payload.installation_id,
            machine_id=payload.machine_id,
            computer_name=payload.computer_name,
            app_version=payload.app_version,
        )
    except EntitlementError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ProActivationResponse(
        success=True,
        entitlement_id=entitlement.id,
        status=entitlement.status,
        signed_package=entitlement.signed_package or "",
        expires_at=entitlement.expires_at,
    )


@router.post("/heartbeat", response_model=ProHeartbeatResponse)
def entitlement_heartbeat(
    payload: ProHeartbeatRequest,
    db: Session = Depends(get_db),
):
    service = EntitlementService(db)
    entitlement = service.get(payload.entitlement_id)
    if entitlement is None:
        raise HTTPException(status_code=404, detail="Pro entitlement not found")

    # Heartbeat is informational. It must never disable Core when the server is unavailable.
    status_value = service.refresh_status(entitlement)
    active = status_value == "active"

    if active:
        device = db.query(EntitlementDeviceService.__annotations__.get("return", object)).first() if False else None
        binding = db.query(__import__("app.models.entitlement_device", fromlist=["EntitlementDevice"]).EntitlementDevice).filter(
            __import__("app.models.entitlement_device", fromlist=["EntitlementDevice"]).EntitlementDevice.entitlement_id == entitlement.id
        ).first()
        if binding:
            binding.last_verified_at = __import__("app.utils.time", fromlist=["utcnow"]).utcnow()
            db.commit()

    return ProHeartbeatResponse(
        success=True,
        entitlement_id=entitlement.id,
        status=status_value,
        pro_active=active,
        expires_at=entitlement.expires_at,
    )


@router.post("/device-change")
def change_device(
    payload: ProDeviceChangeRequest,
    db: Session = Depends(get_db),
):
    service = EntitlementService(db)
    entitlement = service.get(payload.entitlement_id)
    if entitlement is None:
        raise HTTPException(status_code=404, detail="Pro entitlement not found")
    if not service.is_active(entitlement):
        raise HTTPException(status_code=403, detail="Pro entitlement is not active")

    try:
        bindings = EntitlementDeviceService(db)
        old_binding = None
        for binding in entitlement.devices:
            if binding.device.machine_id == payload.old_machine_id and binding.status == "active":
                old_binding = binding
                break
        if old_binding is not None:
            bindings.unbind(old_binding)

        new_device = bindings.get_or_create_device(
            machine_id=payload.new_machine_id,
            license_id=entitlement.legacy_license_id,
            computer_name=payload.computer_name,
        )
        bindings.bind(entitlement, new_device)
        package = service.issue_signed_package(
            entitlement,
            installation_id=payload.installation_id,
            machine_id=payload.new_machine_id,
        )
        db.commit()
    except EntitlementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "entitlement_id": entitlement.id,
        "status": entitlement.status,
        "signed_package": package,
        "expires_at": entitlement.expires_at,
    }


@router.get("/{entitlement_id}")
def get_entitlement(
    entitlement_id: str,
    db: Session = Depends(get_db),
):
    from uuid import UUID
    service = EntitlementService(db)
    entitlement = service.get(UUID(entitlement_id))
    if entitlement is None:
        raise HTTPException(status_code=404, detail="Pro entitlement not found")

    service.refresh_status(entitlement)
    return {
        "id": entitlement.id,
        "product_code": entitlement.product_code,
        "edition": entitlement.edition,
        "status": entitlement.status,
        "starts_at": entitlement.starts_at,
        "expires_at": entitlement.expires_at,
        "max_devices": entitlement.max_devices,
        "activation_count": entitlement.activation_count,
        "features": service.get_feature_snapshot(entitlement),
    }


@router.post("/verify")
def verify_entitlement(
    payload: ProActivationRequest,
):
    from app.utils.entitlement_crypto import verify_signed_entitlement
    try:
        package = verify_signed_entitlement(payload.activation_token)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "valid": True,
        "entitlement_id": package.entitlement.id,
        "product_code": package.entitlement.product_code,
        "edition": package.entitlement.edition,
        "machine_id": package.entitlement.machine_id,
        "installation_id": package.entitlement.installation_id,
        "expires_at": package.entitlement.expires_at,
        "features": package.entitlement.features,
    }


@router.post("/feature-check", response_model=ProFeatureCheckResponse)
def feature_check(
    payload: ProFeatureCheckRequest,
    db: Session = Depends(get_db),
):
    service = EntitlementService(db)
    entitlement = service.get(payload.entitlement_id)
    if entitlement is None:
        return ProFeatureCheckResponse(
            feature_code=payload.feature_code,
            allowed=False,
            entitlement_status=None,
        )
    return ProFeatureCheckResponse(
        feature_code=payload.feature_code,
        allowed=service.has_feature(entitlement, payload.feature_code),
        entitlement_status=service.refresh_status(entitlement),
    )
