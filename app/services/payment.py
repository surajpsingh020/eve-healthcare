import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.booking import Booking, BookingStatus, BOOKING_TRANSITIONS
from app.models.payment import Payment, PaymentStatus
from app.models.webhook_event import WebhookEvent


def process_payment(
    db: Session,
    booking_id: int,
    user_id: int,
    simulate_result: str,
) -> Payment:
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")

    # If a payment already exists for this booking, return it deterministically
    existing_payment = db.query(Payment).filter(Payment.booking_id == booking_id).first()
    if existing_payment:
        return existing_payment

    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Booking is {booking.status.value}, only PENDING bookings can be paid",
        )

    payment_status = PaymentStatus.SUCCESS if simulate_result == "SUCCESS" else PaymentStatus.FAILED
    booking_status = BookingStatus.CONFIRMED if payment_status == PaymentStatus.SUCCESS else BookingStatus.FAILED

    payment = Payment(
        booking_id=booking_id,
        provider_payment_id=f"sim_{uuid.uuid4().hex[:16]}",
        amount=booking.amount,
        status=payment_status,
    )
    booking.status = booking_status

    db.add(payment)
    db.commit()
    db.refresh(payment)

    logger.info(
        "Payment processed: payment_id=%d booking_id=%d result=%s",
        payment.id, booking_id, payment_status.value,
    )
    return payment


def process_webhook(db: Session, event_id: str, event_type: str, payment_id: int, event_status: str) -> dict:
    """
    Process a payment webhook event. Uses the DB UNIQUE constraint on provider_event_id
    as the authoritative idempotency mechanism — if two identical webhooks arrive
    simultaneously, only one INSERT will succeed.
    """
    # Record the webhook event first — the UNIQUE constraint prevents duplicates
    webhook_event = WebhookEvent(
        provider_event_id=event_id,
        event_type=event_type,
        payload={"event_id": event_id, "event_type": event_type, "payment_id": payment_id, "status": event_status},
    )
    db.add(webhook_event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.info("Duplicate webhook event ignored: event_id=%s", event_id)
        return {"status": "already_processed", "event_id": event_id}

    # Lock the payment row to prevent concurrent modifications
    payment = db.execute(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    ).scalar_one_or_none()

    if not payment:
        # Still commit the webhook_event so we don't reprocess on retry
        webhook_event.processed_at = datetime.now(timezone.utc)
        db.commit()
        logger.warning("Webhook references unknown payment: payment_id=%d event_id=%s", payment_id, event_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    # If payment is already in a terminal state, skip processing
    if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.FAILED):
        webhook_event.processed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "Webhook skipped — payment already terminal: payment_id=%d current=%s event_status=%s",
            payment_id, payment.status.value, event_status,
        )
        return {"status": "already_processed", "event_id": event_id}

    # Apply state transition
    new_payment_status = PaymentStatus.SUCCESS if event_status == "SUCCESS" else PaymentStatus.FAILED
    payment.status = new_payment_status

    # Update booking accordingly
    booking = db.get(Booking, payment.booking_id)
    if booking:
        new_booking_status = BookingStatus.CONFIRMED if new_payment_status == PaymentStatus.SUCCESS else BookingStatus.FAILED
        allowed = BOOKING_TRANSITIONS.get(booking.status, set())
        if new_booking_status in allowed:
            booking.status = new_booking_status

    webhook_event.processed_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "Webhook processed: event_id=%s payment_id=%d new_status=%s",
        event_id, payment_id, new_payment_status.value,
    )
    return {"status": "processed", "event_id": event_id}
