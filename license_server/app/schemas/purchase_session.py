from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class PurchaseSessionCreate(BaseModel):
    fingerprint: str = Field(min_length=5, max_length=255)
    product_code: str = Field(default="cbt", min_length=1, max_length=80)
    version: str = Field(default="1.0", min_length=1, max_length=50)
    plan_code: str = Field(min_length=1, max_length=50)
    duration_months: int | None = None
    edition: str | None = Field(default=None, max_length=50)
    installation_id: str | None = Field(default=None, max_length=255)
    machine_id: str | None = Field(default=None, max_length=255)

    amount: Decimal | None = None

    currency: str | None = None
    customer_name: str | None = Field(default=None, max_length=150)
    customer_email: EmailStr | None = None
    customer_phone: str | None = Field(default=None, max_length=50)
    school_name: str | None = Field(default=None, max_length=150)
    gateway: str | None = Field(default=None, max_length=50)
    payment_reference: str | None = Field(default=None, max_length=100)


class PurchaseSessionRead(BaseModel):
    id: UUID
    fingerprint: str
    product_code: str
    version: str
    plan_code: str
    duration_months: int
    amount: Decimal
    currency: str
    customer_name: str
    customer_email: str
    customer_phone: str | None
    school_name: str
    payment_reference: str | None
    gateway: str | None
    gateway_response: str | None = None
    status: str
    completed: bool
    retry_count: int
    expires_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None = None
    activation_token: str | None = None

    model_config = {"from_attributes": True}


class CompletePaymentRequest(BaseModel):
    session_id: UUID | None = None
    payment_reference: str | None = Field(default=None, max_length=100)
    gateway_reference: str | None = Field(default=None, max_length=255)
    gateway_transaction_id: str | None = Field(default=None, max_length=150)
    gateway_response: str | None = None


class PublicActivationStartRequest(PurchaseSessionCreate):
    pass


class PublicStatusResponse(BaseModel):
    session: PurchaseSessionRead
    license_ready: bool = False
    activation_token: str | None = None

class PurchaseInitializationRequest(BaseModel):

    product_slug: str

    plan_slug: str

    fingerprint: str

    installation_id: str

    computer_name: str

    metadata: dict | None = None


class PurchaseInitializationResponse(BaseModel):

    purchase_id: str

    checkout_url: str

    poll_token: str

    expires_at: str