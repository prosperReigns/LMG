from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from pydantic import BaseModel, Field


class EntitlementPayload(BaseModel):
    id: UUID
    product_code: str
    edition: str
    installation_id: str
    machine_id: str
    issued_at: datetime
    starts_at: datetime
    expires_at: datetime | None
    features: dict[str, bool] = Field(default_factory=dict)


class SignedEntitlement(BaseModel):
    package_type: str = "examcenter_pro_entitlement"
    package_version: int = 2
    entitlement: EntitlementPayload
    public_key_version: str = "v2"
    checksum: str
    signature: str


def _canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _checksum(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _keys_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "keys"


def _load_private_key():
    path = _keys_dir() / "private.pem"
    with path.open("rb") as handle:
        return serialization.load_pem_private_key(handle.read(), password=None)


def _load_public_key():
    path = _keys_dir() / "public.pem"
    with path.open("rb") as handle:
        return serialization.load_pem_public_key(handle.read())


def build_signed_entitlement(
    *,
    entitlement_id: UUID,
    installation_id: str,
    machine_id: str,
    starts_at: datetime,
    expires_at: datetime | None,
    features: dict[str, bool],
    issued_at: datetime | None = None,
    public_key_version: str = "v2",
) -> str:
    issued_at = issued_at or datetime.now(timezone.utc)
    payload = EntitlementPayload(
        id=entitlement_id,
        product_code="examcenter",
        edition="pro",
        installation_id=installation_id,
        machine_id=machine_id,
        issued_at=issued_at,
        starts_at=starts_at,
        expires_at=expires_at,
        features=features,
    ).model_dump(mode="json")

    checksum = _checksum(payload)
    private_key = _load_private_key()
    signature = private_key.sign(
        _canonical_json(payload),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    package = {
        "package_type": "examcenter_pro_entitlement",
        "package_version": 2,
        "entitlement": payload,
        "public_key_version": public_key_version,
        "checksum": checksum,
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    return json.dumps(package, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def verify_signed_entitlement(document: str | dict[str, Any]) -> SignedEntitlement:
    raw = json.loads(document) if isinstance(document, str) else document
    package = SignedEntitlement.model_validate(raw)
    payload = package.entitlement.model_dump(mode="json")
    expected_checksum = _checksum(payload)

    if package.checksum != expected_checksum:
        raise ValueError("Entitlement checksum mismatch")

    public_key = _load_public_key()
    try:
        public_key.verify(
            base64.b64decode(package.signature),
            _canonical_json(payload),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except Exception as exc:
        raise ValueError("Entitlement signature verification failed") from exc

    now = datetime.now(timezone.utc)
    if package.entitlement.starts_at > now:
        raise ValueError("Entitlement is not active yet")
    if package.entitlement.expires_at is not None and package.entitlement.expires_at <= now:
        raise ValueError("Entitlement has expired")

    return package
