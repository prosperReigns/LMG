from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.purchase_session import PurchaseSession
from app.schemas.entitlement_api import ProPurchaseRequest, ProPurchaseResponse
from app.schemas.purchase_session import PurchaseSessionCreate
from app.services.purchase_session_service import start_purchase, get_purchase_status


router = APIRouter(
    prefix="/api/v2/public/purchases",
    tags=["Pro Purchases"],
)


@router.post("/", response_model=ProPurchaseResponse)
def create_pro_purchase(
    payload: ProPurchaseRequest,
    db: Session = Depends(get_db),
):
    if payload.product_code != "examcenter" or payload.edition != "pro":
        raise HTTPException(status_code=400, detail="Only the Examcenter Pro product is supported")

    legacy = PurchaseSessionCreate(
        fingerprint=payload.machine_id,
        product_code="examcenter",
        version=payload.version,
        plan_code=f"pro_{payload.duration_months}_months",
        duration_months=payload.duration_months,
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        customer_phone=payload.customer_phone,
        school_name=payload.school_name,
    )
    try:
        result = start_purchase(db, legacy)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # start_purchase currently uses legacy pricing/plan resolution. The v2 contract
    # is exposed here without changing the legacy purchase implementation until the
    # pricing/commerce migration is completed.
    session = db.get(PurchaseSession, result["purchase_id"])
    return ProPurchaseResponse(
        purchase_id=session.id,
        status=session.status,
        product_code="examcenter",
        edition="pro",
        duration_months=session.duration_months,
        amount=session.amount,
        currency=session.currency,
        checkout_url=session.checkout_url,
        poll_token=session.poll_token,
        expires_at=session.expires_at,
    )


@router.get("/{purchase_id}")
def get_pro_purchase(
    purchase_id: str,
    db: Session = Depends(get_db),
):
    from uuid import UUID
    result = get_purchase_status(db, UUID(purchase_id))
    return {
        "purchase_id": purchase_id,
        "status": result["session"].status,
        "completed": result["session"].completed,
        "entitlement_id": result["session"].entitlement_id,
        "activation_token": result["activation_token"],
    }
