from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums.purchase_status import PurchaseStatus
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.outbox_event import OutboxEvent
from app.models.payment import Payment
from app.models.purchase_session import PurchaseSession
from app.models.receipt import Receipt
from app.models.school import School
from app.models.license import License
from app.repositories.activation_repository import (
    create_activation_record,
    get_activation_for_machine,
)
from app.repositories.activation_token_repository import get_by_id
from app.repositories.customer_repository import create_customer, get_customer_by_email
from app.repositories.invoice_repository import create_invoice, mark_invoice_paid
from app.repositories.license_device_repository import (
    create_device,
    get_device_by_machine_id,
    save_device,
)
from app.repositories.license_history_repository import create_history_record
from app.repositories.license_repository import create_license_record, get_license_by_id, persist_license
from app.repositories.payment_repository import (
    create_payment_record as create_payment_record_repository,
    get_payment_by_reference,
)
from app.repositories.purchase_session_repository import (
    increment_retry_count,
    mark_purchase_completed,
    save_purchase_session,
)
from app.repositories.receipt_repository import create_receipt, get_receipt_by_payment
from app.repositories.school_repository import create_school, get_school_by_name
from app.services.activation_token_service import create_activation_token
from app.services.audit_service import record_audit_event
from app.services.invoice_service import generate_invoice_number
from app.services.license_service import create_signed_license, normalize_license_type
from app.services.entitlement_service import EntitlementService
from app.services.entitlement_renewal_service import EntitlementRenewalService
from app.models.entitlement import Entitlement
from app.services.purchase_state_machine import validate_transition
from app.services.receipt_service import generate_receipt_number
from app.utils.time import is_expired, is_token_deliverable, utcnow

logger = logging.getLogger(__name__)


def _set_status(db: Session, purchase_session: PurchaseSession, status_value: PurchaseStatus) -> None:
    if purchase_session.status == status_value.value:
        return
    validate_transition(purchase_session.status, status_value)
    purchase_session.status = status_value.value

    print(
        f"STATUS: {purchase_session.id} -> {purchase_session.status}"
    )
    save_purchase_session(db, purchase_session)
    record_audit_event(
        db,
        action="purchase_status_changed",
        entity_type="purchase_session",
        entity_id=str(purchase_session.id),
        description=f"Purchase moved to {status_value.value}",
    )


def _ensure_not_expired(purchase_session: PurchaseSession) -> None:
    if is_expired(purchase_session.expires_at):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Purchase session has expired.",
        )


def _get_or_create_customer(db: Session, purchase_session: PurchaseSession):
    if purchase_session.customer_id:
        customer = db.get(Customer, purchase_session.customer_id)
        if customer is not None:
            return customer

    customer = get_customer_by_email(db, purchase_session.customer_email)
    if customer is None:
        customer = create_customer(
            db,
            name=purchase_session.customer_name,
            email=purchase_session.customer_email,
            phone=purchase_session.customer_phone,
            country=None,
            is_active=True,
        )
    purchase_session.customer_id = customer.id
    _set_status(db, purchase_session, PurchaseStatus.CUSTOMER_CREATED)
    return customer


def _get_or_create_school(db: Session, purchase_session: PurchaseSession, customer):
    if purchase_session.school_id:
        school = db.get(School, purchase_session.school_id)
        if school is not None:
            return school

    school = get_school_by_name(
        db,
        purchase_session.school_name,
        customer_id=customer.id,
    )
    if school is None:
        school = create_school(
            db,
            customer_id=customer.id,
            name=purchase_session.school_name,
            code=None,
            address=None,
            contact_email=purchase_session.customer_email,
            contact_phone=purchase_session.customer_phone,
            is_active=True,
        )
    purchase_session.school_id = school.id
    _set_status(db, purchase_session, PurchaseStatus.SCHOOL_CREATED)
    return school


def _get_or_create_license(db: Session, purchase_session: PurchaseSession, school):
    if purchase_session.license_id:
        license_obj = get_license_by_id(db, purchase_session.license_id)
        if license_obj is not None:
            return license_obj

    existing_license = db.scalar(
        select(License).where(
            License.school_id == school.id,
            License.machine_fingerprint == purchase_session.fingerprint,
        )
    )

    if existing_license:
        print("USING EXISTING LICENSE")

        purchase_session.license_id = existing_license.id

        save_purchase_session(
            db,
            purchase_session,
        )

        _set_status(
            db,
            purchase_session,
            PurchaseStatus.LICENSE_CREATED,
        )

        return existing_license

    license_type = normalize_license_type(purchase_session.plan_code)
    issued_at = utcnow()

    license_obj = create_license_record(
        db,
        school_id=school.id,
        machine_fingerprint=purchase_session.fingerprint,
        license_type=license_type,
        plan_name=purchase_session.plan_code,
        duration_months=purchase_session.duration_months,
        is_trial=license_type in {"demo", "trial"},
        issued_at=issued_at,
        expiry_at=None,
        payment_status="paid",
        flutterwave_transaction_id=purchase_session.gateway_transaction_id,
        flutterwave_reference=purchase_session.payment_reference,
        amount_paid=purchase_session.amount,
        currency=purchase_session.currency,
        signed_license=None,
        activation_count=0,
        max_activations=1,
        version=1,
    )
    
    signed_document = create_signed_license(
        license_id=license_obj.id,
        school_id=school.id,
        school_code=school.code,
        school=school.name,
        machine=purchase_session.fingerprint,
        product_code=purchase_session.product_code,
        product_name="CBT Examination Software",
        license_type=license_type,
        plan_code=purchase_session.plan_code,
        plan_name=purchase_session.plan_code,
        duration_months=purchase_session.duration_months,
        is_trial=license_type in {"demo", "trial"},
        issued_at=license_obj.issued_at,
        expiry=license_obj.expiry_at,
        version=license_obj.version,
    )

    license_obj.signed_license = signed_document.model_dump_json()

    license_obj.issued_at = signed_document.issued_at
    license_obj.expiry_at = signed_document.expiry

    persist_license(
        db,
        license_obj,
    )

    purchase_session.license_id = license_obj.id

    save_purchase_session(
        db,
        purchase_session,
    )

    create_history_record(
        db,
        license_id=license_obj.id,
        version=license_obj.version,
        license_type=license_obj.license_type,
        issued_at=license_obj.issued_at,
        expiry_at=license_obj.expiry_at,
        signed_license=license_obj.signed_license,
    )
    purchase_session.license_id = license_obj.id
    _set_status(db, purchase_session, PurchaseStatus.LICENSE_CREATED)
    return license_obj


def _get_or_create_entitlement(db: Session, purchase_session: PurchaseSession, customer, school, license_obj):
    service = EntitlementService(db)
    existing = service.get(purchase_session.entitlement_id) if purchase_session.entitlement_id else None
    if existing is None:
        existing = db.scalar(select(Entitlement).where(Entitlement.legacy_license_id == license_obj.id))
    if existing is None:
        existing = service.create_pro_entitlement(
            customer_id=customer.id,
            school_id=school.id,
            starts_at=license_obj.issued_at,
            expires_at=license_obj.expiry_at,
            max_devices=max(license_obj.max_activations or 1, 1),
            legacy_license_id=license_obj.id,
        )
    elif purchase_session.duration_months:
        EntitlementRenewalService(db).renew(existing, duration_days=max(purchase_session.duration_months * 30, 1), amount=purchase_session.amount, currency=purchase_session.currency, plan_code=purchase_session.plan_code)
    purchase_session.entitlement_id = existing.id
    save_purchase_session(db, purchase_session)
    db.flush()
    return existing

def _get_or_create_invoice(db: Session, purchase_session: PurchaseSession, license_obj, entitlement=None) -> Invoice:
    if purchase_session.invoice_id:
        invoice = db.get(Invoice, purchase_session.invoice_id)
        if invoice is not None:
            return invoice

    existing_invoice = db.scalar(
        select(Invoice).where(
            Invoice.license_id == license_obj.id
        )
    )

    if existing_invoice is not None:
        print("USING EXISTING INVOICE")

        purchase_session.invoice_id = existing_invoice.id

        save_purchase_session(
            db,
            purchase_session,
        )

        _set_status(
            db,
            purchase_session,
            PurchaseStatus.INVOICE_CREATED,
        )

        return existing_invoice

    invoice = Invoice(
        license_id=license_obj.id,
        entitlement_id=entitlement.id if entitlement is not None else None,
        school_id=license_obj.school_id,
        invoice_number=generate_invoice_number(db),
        description=f"Examcenter Pro {purchase_session.duration_months}-month purchase",
        amount=purchase_session.amount,
        currency=purchase_session.currency,
        status="paid",
        due_date=None,
        paid_at=utcnow(),
    )
    create_invoice(db, invoice)
    purchase_session.invoice_id = invoice.id
    _set_status(db, purchase_session, PurchaseStatus.INVOICE_CREATED)
    return invoice


def _get_or_create_payment(db: Session, purchase_session: PurchaseSession, customer, school, invoice) -> Payment:
    if purchase_session.payment_id:
        payment = db.get(Payment, purchase_session.payment_id)

        if payment is not None:
            return payment

    payment = db.scalar(
        select(Payment).where(
            Payment.invoice_id == invoice.id,
            Payment.status == "pending",
        )
    )

    if payment is not None:

        payment.status = "successful"

        payment.gateway_reference = purchase_session.gateway_reference

        payment.gateway_transaction_id = (
            purchase_session.gateway_transaction_id
        )

        payment.raw_payload = purchase_session.gateway_response

        payment.verified_at = utcnow()

        payment.paid_at = utcnow()

        db.add(payment)

        db.flush()

        purchase_session.payment_id = payment.id

        mark_invoice_paid(
            db,
            invoice,
        )

        _set_status(
            db,
            purchase_session,
            PurchaseStatus.PAYMENT_RECORDED,
        )

        return payment

    if not purchase_session.payment_reference:
        purchase_session.payment_reference = f"PS-{purchase_session.id}"

    payment = get_payment_by_reference(db, purchase_session.payment_reference)

    if payment is None:
        payment = create_payment_record_repository(
            db,
            customer_id=customer.id,
            school_id=school.id,
            invoice_id=invoice.id,
            payment_reference=purchase_session.payment_reference,
            gateway=purchase_session.gateway,
            amount=purchase_session.amount,
            currency=purchase_session.currency,
            payment_type=purchase_session.plan_code,
            status="successful",
            gateway_reference=purchase_session.gateway_reference,
            gateway_transaction_id=purchase_session.gateway_transaction_id,
            raw_payload=purchase_session.gateway_response,
        )
        payment.verified_at = utcnow()
        payment.paid_at = utcnow()
        db.add(payment)
        db.flush()
    else:
        payment.status = "successful"
        payment.verified_at = payment.verified_at or utcnow()
        payment.paid_at = payment.paid_at or utcnow()
        payment.raw_payload = payment.raw_payload or purchase_session.gateway_response
        payment.gateway = purchase_session.gateway
        payment.gateway_reference = purchase_session.gateway_reference
        payment.gateway_transaction_id = purchase_session.gateway_transaction_id
        payment.currency = purchase_session.currency
        payment.amount = purchase_session.amount
        payment.payment_type = purchase_session.plan_code

        db.add(payment)
        db.flush()

    mark_invoice_paid(db, invoice)
    purchase_session.payment_id = payment.id
    _set_status(db, purchase_session, PurchaseStatus.PAYMENT_RECORDED)
    return payment


def _get_or_create_device(db: Session, purchase_session: PurchaseSession, license_obj):
    device = get_device_by_machine_id(db, purchase_session.fingerprint)
    if device is None:
        device = create_device(
            db,
            license_id=license_obj.id,
            machine_id=purchase_session.fingerprint,
        )
    else:
        device.license_id = license_obj.id
        save_device(db, device)
    if device.blacklisted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device is blacklisted.")
    purchase_session.device_id = device.id
    _set_status(db, purchase_session, PurchaseStatus.DEVICE_REGISTERED)
    return device

def _get_or_create_activation(
    db: Session,
    purchase_session: PurchaseSession,
    license_obj,
    device,
):
    activation = get_activation_for_machine(
        db,
        license_obj.id,
        purchase_session.fingerprint,
    )

    if activation is None:
        activation = create_activation_record(
            db,
            license_id=license_obj.id,
            device_id=device.id,
            school_id=license_obj.school_id,
            machine_id=purchase_session.fingerprint,
            computer_name=None,
            ip_address=None,
        )

        license_obj.activation_count = (
            license_obj.activation_count or 0
        ) + 1

        license_obj.last_activation_at = utcnow()

        device.activation_count = (
            device.activation_count or 0
        ) + 1

        db.add_all([
            license_obj,
            device,
        ])

        db.flush()

    purchase_session.activation_id = activation.id

    _set_status(
        db,
        purchase_session,
        PurchaseStatus.ACTIVATED,
    )

    return activation

def _get_or_create_receipt(db: Session, purchase_session: PurchaseSession, payment) -> Receipt:
    if purchase_session.receipt_id:
        receipt = db.get(Receipt, purchase_session.receipt_id)
        if receipt is not None:
            return receipt

    receipt = get_receipt_by_payment(db, payment.id)

    if receipt is not None:
        purchase_session.receipt_id = receipt.id
        save_purchase_session(
            db,
            purchase_session,
        )
        return receipt

    if receipt is None:
        receipt = Receipt(
            receipt_number=generate_receipt_number(db),
            invoice_id=payment.invoice_id,
            payment_id=payment.id,
            customer_id=payment.customer_id,
            school_id=payment.school_id,
            amount=payment.amount,
            currency=payment.currency,
            status="issued",
        )
        create_receipt(db, receipt)
    purchase_session.receipt_id = receipt.id
    _set_status(db, purchase_session, PurchaseStatus.RECEIPT_CREATED)
    return receipt


def _queue_outbox_event(db: Session, purchase_session: PurchaseSession, payload: dict[str, Any]) -> None:
    existing = db.scalar(
        select(OutboxEvent).where(
            OutboxEvent.event_type == "purchase.completed",
            OutboxEvent.aggregate_id == purchase_session.id,
        )
    )
    if existing is not None:
        return

    event = OutboxEvent(
        event_type="purchase.completed",
        aggregate_type="purchase_session",
        aggregate_id=purchase_session.id,
        payload=json.dumps(
            payload,
            default=str,
        ),
        processed=False,
        retry_count=0,
    )
    db.add(event)
    db.flush()


def _get_or_create_activation_token(db: Session, purchase_session: PurchaseSession, license_obj, entitlement=None):
    token = get_by_id(db, purchase_session.activation_token_id) if purchase_session.activation_token_id else None
    if is_token_deliverable(token):
        return token
    if token is not None and (token.used_at is not None or token.revoked_at is not None):
        return token

    token = create_activation_token(
        db,
        purchase_session=purchase_session,
        license=license_obj,
        entitlement=entitlement,
        fingerprint=purchase_session.machine_id or purchase_session.fingerprint,
    )
    purchase_session.activation_token_id = token.id
    save_purchase_session(db, purchase_session)
    return token


def complete_purchase(
    db: Session,
    purchase_session: PurchaseSession,
) -> dict[str, Any]:
    if purchase_session.completed:
        license_obj = get_license_by_id(db, purchase_session.license_id) if purchase_session.license_id else None
        entitlement = db.get(Entitlement, purchase_session.entitlement_id) if purchase_session.entitlement_id else None
        token = (
            _get_or_create_activation_token(db, purchase_session, license_obj, entitlement)
            if license_obj is not None or entitlement is not None
            else get_by_id(db, purchase_session.activation_token_id)
            if purchase_session.activation_token_id
            else None
        )
        db.commit()
        return {
            "status": "completed",
            "session_id": str(purchase_session.id),
            "activation_token": token.token if is_token_deliverable(token) else None,
            "license_id": str(purchase_session.license_id) if purchase_session.license_id else None,
        }

    try:
        _ensure_not_expired(purchase_session)
        _set_status(db, purchase_session, PurchaseStatus.PAYMENT_VERIFIED)

        print("START STATUS:", purchase_session.status)
        customer = _get_or_create_customer(db, purchase_session)

        
        print("AFTER CUSTOMER:", purchase_session.status)
        school = _get_or_create_school(db, purchase_session, customer)

        

        print("AFTER SCHOOL:", purchase_session.status)
        license_obj = _get_or_create_license(db, purchase_session, school)

        print("AFTER LICENSE:", purchase_session.status)
        entitlement = _get_or_create_entitlement(db, purchase_session, customer, school, license_obj)
        invoice = _get_or_create_invoice(db, purchase_session, license_obj, entitlement)

        print("AFTER INVOICE:", purchase_session.status)
        payment = _get_or_create_payment(db, purchase_session, customer, school, invoice)
        device = _get_or_create_device(db, purchase_session, license_obj)
        activation = _get_or_create_activation(db, purchase_session, license_obj, device)
        receipt = _get_or_create_receipt(db, purchase_session, payment)
        activation_token = _get_or_create_activation_token(db, purchase_session, license_obj, entitlement)
        mark_purchase_completed(db, purchase_session)
        purchase_session.completed = True

        save_purchase_session(
            db,
            purchase_session,
        )
        _queue_outbox_event(
            db,
            purchase_session,
            {
                "customer_id": str(customer.id),
                "school_id": str(school.id),
                "license_id": str(license_obj.id),
                "entitlement_id": str(entitlement.id),
                "invoice_id": str(invoice.id),
                "payment_id": str(payment.id),
                "activation_id": str(activation.id),
                "receipt_id": str(receipt.id),
            },
        )
        record_audit_event(
            db,
            action="purchase_completed",
            entity_type="purchase_session",
            entity_id=str(purchase_session.id),
            description="Self-service purchase completed automatically.",
        )
        db.commit()
        return {
            "status": "completed",
            "session_id": str(purchase_session.id),
            "activation_token": activation_token.token,
            "license_id": str(license_obj.id),
            "entitlement_id": str(entitlement.id),
        }
    except HTTPException as exc:
        db.rollback()
        if exc.status_code == status.HTTP_410_GONE:
            expired_session = db.get(PurchaseSession, purchase_session.id)
            if expired_session is not None:
                expired_session.status = PurchaseStatus.EXPIRED.value
                save_purchase_session(db, expired_session)
                record_audit_event(
                    db,
                    action="purchase_expired",
                    entity_type="purchase_session",
                    entity_id=str(expired_session.id),
                    description="Purchase session expired before orchestration completed.",
                )
                db.commit()
        raise
    except Exception:
        db.rollback()
        session_id = purchase_session.id
        failed_session = db.get(PurchaseSession, session_id)
        if failed_session is not None:
            increment_retry_count(db, failed_session)
            failed_session.status = PurchaseStatus.FAILED.value
            save_purchase_session(db, failed_session)

            record_audit_event(
                db,
                action="purchase_failed",
                entity_type="purchase_session",
                entity_id=str(
                    failed_session.id
                ),
                description="Automatic purchase orchestration failed.",
            )
            
            db.commit()
        logger.exception("Purchase orchestration failed for session %s", session_id)
        raise


def resume_purchase(db: Session, purchase_session: PurchaseSession) -> dict[str, Any]:
    return complete_purchase(db, purchase_session)
