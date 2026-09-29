from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.booking import Booking, BookingStatus, BOOKING_TRANSITIONS
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest


def create_booking(
    db: Session,
    user_id: int,
    centre_id: int,
    test_id: int,
    appointment_at: datetime,
) -> Booking:
    centre = db.get(DiagnosticCentre, centre_id)
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")

    test = db.get(DiagnosticTest, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    centre_test = (
        db.query(CentreTest)
        .filter(CentreTest.centre_id == centre_id, CentreTest.test_id == test_id)
        .first()
    )
    if not centre_test:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This test is not offered by the selected centre",
        )

    # Treat naive datetimes as UTC
    if appointment_at.tzinfo is None:
        appointment_at = appointment_at.replace(tzinfo=timezone.utc)

    if appointment_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Appointment must be in the future",
        )

    # Capture the current price — this snapshot won't change even if the centre updates pricing later
    booking = Booking(
        user_id=user_id,
        centre_id=centre_id,
        test_id=test_id,
        appointment_at=appointment_at,
        amount=centre_test.price,
        status=BookingStatus.PENDING,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    logger.info("Booking created: id=%d user=%d centre=%d test=%d amount=%s", booking.id, user_id, centre_id, test_id, centre_test.price)
    return booking


def cancel_booking(db: Session, booking_id: int, user_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")

    _transition_booking(booking, BookingStatus.CANCELLED)
    db.commit()
    db.refresh(booking)

    logger.info("Booking cancelled: id=%d user=%d", booking_id, user_id)
    return booking


def _transition_booking(booking: Booking, new_status: BookingStatus) -> None:
    """Validates and applies a booking state transition."""
    allowed = BOOKING_TRANSITIONS.get(booking.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition booking from {booking.status.value} to {new_status.value}",
        )
    booking.status = new_status
