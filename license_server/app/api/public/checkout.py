from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi import Request
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.purchase_session_service import (
    complete_free_trial,
)
from app.services.purchase_orchestration_service import (
            complete_purchase,
        )
from app.enums.purchase_status import PurchaseStatus
from fastapi.responses import RedirectResponse

# rate limiting
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address)
except Exception:
    # Fallback no-op limiter if slowapi is not available
    class _NoopLimiter:
        def limit(self, *args, **kwargs):
            def _decorator(func):
                return func
            return _decorator

    limiter = _NoopLimiter()

from app.services.checkout_service import CheckoutService
from fastapi.responses import JSONResponse
from app.services.checkout_page_service import (
    get_checkout_page,
)
from app.services.payment_initialization_service import PaymentInitializationService

from app.web.templates import templates

router = APIRouter(
    prefix="/api/public/checkout",
    tags=["Public Checkout"],
)


@limiter.limit("5/minute")
@router.get("/{checkout_token}")
def get_checkout(
    request: Request,
    checkout_token: str,
    db: Session = Depends(get_db),
):
    purchase = get_checkout_page(
        db,
        checkout_token,
    )

    # ------------------------------------------------------------
    # FREE TRIAL
    # ------------------------------------------------------------

    if purchase.plan_code == "trial":

        # A trial is treated as payment-verified immediately.
        if purchase.status == PurchaseStatus.PENDING.value:

            purchase.status = PurchaseStatus.PAYMENT_VERIFIED.value
            purchase.payment_status = "trial"
            purchase.gateway = None
            purchase.gateway_reference = None
            purchase.gateway_transaction_id = None

            db.add(purchase)
            db.commit()
            db.refresh(purchase)

        # Complete the exact same orchestration used
        # after successful paid payment.
        complete_purchase(
            db,
            purchase,
        )

        db.refresh(purchase)

        # --------------------------------------------------------
        # Return to the CBT application.
        # --------------------------------------------------------

        return_url = request.query_params.get("return_url")

        if not return_url:
            raise HTTPException(
                status_code=400,
                detail="Return URL missing.",
            )

        return RedirectResponse(
            url=return_url,
            status_code=303,
        )

    # ------------------------------------------------------------
    # PAID PLANS
    # ------------------------------------------------------------

    payment = PaymentInitializationService(
        db
    ).initialize_payment(
        checkout_token
    )

    return templates.TemplateResponse(
        "public/checkout.html",
        {
            "request": request,
            "checkout_url": payment["authorization_url"],
            "purchase": purchase,
            "trial": False,
        },
    )


@router.get("/{checkout_token}/validate")
def validate_checkout(
    request: Request,
    checkout_token: str,
    db: Session = Depends(get_db),
):
    """
    Validate a checkout token without
    returning all purchase information.
    """

    service = CheckoutService(db)

    session = service.validate_checkout_session(
        checkout_token
    )

    return {

        "valid": True,

        "purchase_id": session.id,

        "status": session.status,

        "expires_at": session.expires_at,

    }


@router.get("/{checkout_token}/summary")
def purchase_summary(
    request: Request,
    checkout_token: str,
    db: Session = Depends(get_db),
):
    """
    Lightweight purchase summary
    used by the checkout page.
    """

    service = CheckoutService(db)

    session = service.checkout_view_model(
        checkout_token
    )

    return {

        "product":

            session["product_code"],

        "version":

            session["version"],

        "plan":

            session["plan_code"],

        "price":

            session["price"],

        "currency":

            session["currency"],

        "duration":

            session["duration_months"],

        "school":

            session["school_name"],

        "status":

            session["status"],

        "expires_at":

            session["expires_at"],

    }

@router.get("/{checkout_token}/status")
def purchase_status(
    request: Request,
    checkout_token: str,
    db: Session = Depends(get_db),
):
    """
    Lightweight polling endpoint used
    by the desktop application.

    This endpoint intentionally returns
    only the current purchase status.
    """

    service = CheckoutService(db)

    return service.purchase_status(
        checkout_token
    )

@router.post("/{checkout_token}/trial")
def start_free_trial(
    checkout_token: str,
    db: Session = Depends(get_db),
):
    return complete_free_trial(
        db,
        checkout_token,
    )