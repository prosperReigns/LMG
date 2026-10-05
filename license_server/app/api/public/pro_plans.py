from fastapi import APIRouter

from app.core.pricing import get_plan


router = APIRouter(
    prefix="/api/v2/public/plans",
    tags=["Pro Plans"],
)


@router.get("")
def list_pro_plans():
    plans = []
    for code in ("6_months", "12_months", "24_months"):
        plan = get_plan(code)
        plans.append({
            "product_code": "examcenter",
            "edition": "pro",
            "offer_code": code,
            "name": f"Examcenter Pro - {plan['name']}",
            "duration_months": plan["duration_months"],
            "duration_days": plan["duration_days"],
            "price": plan["price"],
            "currency": plan["currency"],
        })
    return {"product_code": "examcenter", "edition": "pro", "plans": plans}
