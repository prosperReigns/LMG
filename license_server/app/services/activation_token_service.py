from datetime import timedelta
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.activation_token import ActivationToken
from app.repositories.purchase_session_repository import save_purchase_session
from app.repositories import activation_token_repository
from app.utils.time import as_aware, utcnow


def generate_token() -> str:
    return secrets.token_urlsafe(48)


def create_activation_token(
    db: Session,
    *,
    purchase_session,
    license=None,
    entitlement=None,
    fingerprint: str,
    ttl_minutes: int = 15,
) -> ActivationToken:
    existing = activation_token_repository.get_active_for_purchase(
        db,
        purchase_session.id,
    )
    if existing is not None:
        return existing

    activation_token = ActivationToken(
        token=generate_token(),
        purchase_session_id=purchase_session.id,
        license_id=license.id if license is not None else None,
        entitlement_id=entitlement.id if entitlement is not None else None,
        machine_fingerprint=fingerprint.strip(),
        expires_at=utcnow() + timedelta(minutes=ttl_minutes),
    )
    return activation_token_repository.create(db, activation_token)


class ActivationTokenService:
    def __init__(self, db: Session):
        self.db = db

    def create_for_purchase(
        self,
        purchase_session_id,
        *,
        ttl_minutes: int = 15,
    ) -> ActivationToken:
        from app.models.license import License
        from app.models.purchase_session import PurchaseSession

        purchase_session = self.db.get(PurchaseSession, purchase_session_id)
        if purchase_session is None:
            raise ValueError("Purchase session not found.")

        if purchase_session.license_id is None and purchase_session.entitlement_id is None:
            raise ValueError("Purchase session has no entitlement or license.")

        license_obj = self.db.get(License, purchase_session.license_id)
        if license_obj is None:
            raise ValueError("License not found.")

        token = create_activation_token(
            self.db,
            purchase_session=purchase_session,
            license=license_obj,
            fingerprint=purchase_session.fingerprint,
            ttl_minutes=ttl_minutes,
        )
        purchase_session.activation_token_id = token.id
        save_purchase_session(self.db, purchase_session)
        self.db.commit()
        self.db.refresh(token)
        return token


def validate_token(activation_token: ActivationToken | None) -> None:
    if activation_token is None:
        raise HTTPException(404, "Activation token not found.")
    if activation_token.revoked_at:
        raise HTTPException(403, "Activation token revoked.")
    if activation_token.used_at:
        raise HTTPException(403, "Activation token already used.")
    if as_aware(activation_token.expires_at) < utcnow():
        raise HTTPException(403, "Activation token expired.")


def validate_machine(activation_token: ActivationToken, fingerprint: str) -> None:
    if activation_token.machine_fingerprint != fingerprint.strip():
        raise HTTPException(403, "Machine fingerprint mismatch.")


def consume_token(db: Session, activation_token: ActivationToken) -> ActivationToken:
    return activation_token_repository.mark_used(db, activation_token)
