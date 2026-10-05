from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProPurchaseRequest(BaseModel):
    product_code: str = Field(default="examcenter", min_length=1, max_length=80)
    edition: str = Field(default="pro", min_length=1, max_length=50)
    installation_id: str = Field(min_length=1, max_length=255)
    machine_id: str = Field(min_length=1, max_length=255)
    version: str = Field(default="1.0.0", min_length=1, max_length=50)
    duration_months: int = Field(gt=0, le=120)
    customer_name: str = Field(min_length=1, max_length=150)
    customer_email: str = Field(min_length=3, max_length=255)
    customer_phone: str | None = Field(default=None, max_length=50)
    school_name: str = Field(min_length=1, max_length=150)


class ProPurchaseResponse(BaseModel):
    purchase_id: UUID
    status: str
    product_code: str
    edition: str
    duration_months: int
    amount: Any
    currency: str
    checkout_url: str | None = None
    poll_token: str | None = None
    expires_at: datetime


class ProActivationRequest(BaseModel):
    activation_token: str = Field(min_length=1, max_length=128)
    installation_id: str = Field(min_length=1, max_length=255)
    machine_id: str = Field(min_length=1, max_length=255)
    computer_name: str | None = Field(default=None, max_length=255)
    app_version: str | None = Field(default=None, max_length=50)


class ProActivationResponse(BaseModel):
    success: bool
    entitlement_id: UUID
    status: str
    signed_package: str
    expires_at: datetime | None


class ProHeartbeatRequest(BaseModel):
    entitlement_id: UUID
    installation_id: str = Field(min_length=1, max_length=255)
    machine_id: str = Field(min_length=1, max_length=255)
    app_version: str | None = Field(default=None, max_length=50)


class ProHeartbeatResponse(BaseModel):
    success: bool
    entitlement_id: UUID
    status: str
    pro_active: bool
    expires_at: datetime | None


class ProDeviceChangeRequest(BaseModel):
    entitlement_id: UUID
    old_machine_id: str = Field(min_length=1, max_length=255)
    new_machine_id: str = Field(min_length=1, max_length=255)
    installation_id: str = Field(min_length=1, max_length=255)
    computer_name: str | None = Field(default=None, max_length=255)


class ProFeatureCheckRequest(BaseModel):
    entitlement_id: UUID
    feature_code: str = Field(min_length=1, max_length=100)


class ProFeatureCheckResponse(BaseModel):
    feature_code: str
    allowed: bool
    entitlement_status: str | None
