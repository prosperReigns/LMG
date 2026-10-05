from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.entitlement import Entitlement
from app.repositories.activation_token_repository import get_valid_download_token
from app.services.activation_token_service import consume_token, validate_token
from app.services.entitlement_service import EntitlementService


router = APIRouter(
    prefix="/api/public",
    tags=["Public License"],
)


@router.get("/license/{token}")
def get_license(token: str, db: Session = Depends(get_db)):
    """Legacy download endpoint backed by the new Pro entitlement system.

    The response shape remains {"success": True, "license": ...} so older
    Examcenter clients can continue downloading a signed package.
    """
    activation_token = get_valid_download_token(db, token)
    validate_token(activation_token)

    entitlement = None
    if activation_token.entitlement_id is not None:
        entitlement = db.get(Entitlement, activation_token.entitlement_id)

    if entitlement is not None:
        if not EntitlementService(db).is_active(entitlement):
            raise HTTPException(status_code=403, detail="Pro entitlement is not active")
        license_data = entitlement.signed_package
        if not license_data:
            raise HTTPException(status_code=409, detail="Pro entitlement package is not available")
        consume_token(db, activation_token)
        db.commit()
        return {"success": True, "license": license_data}

    license_obj = activation_token.license
    if license_obj is None or not license_obj.signed_license:
        raise HTTPException(status_code=404, detail="License package not found")

    license_data = license_obj.signed_license
    consume_token(db, activation_token)
    db.commit()
    return {"success": True, "license": license_data}
