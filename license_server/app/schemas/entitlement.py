from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EntitlementFeatureRead(BaseModel):
    feature_code: str
    enabled: bool
    limits: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class EntitlementRead(BaseModel):
    id: UUID
    customer_id: UUID | None
    school_id: UUID | None
    product_code: str
    edition: str
    status: str
    starts_at: datetime
    expires_at: datetime | None
    max_devices: int
    activation_count: int
    package_version: int
    public_key_version: str
    legacy_license_id: UUID | None
    features: list[EntitlementFeatureRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class EntitlementFeatureCheckRequest(BaseModel):
    feature_code: str = Field(min_length=1, max_length=100)


class EntitlementFeatureCheckResponse(BaseModel):
    feature_code: str
    allowed: bool
    entitlement_status: str | None = None
