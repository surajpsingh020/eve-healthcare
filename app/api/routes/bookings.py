from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.booking import Booking
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingResponse
from app.schemas.common import PaginatedResponse
from app.services.booking import cancel_booking, create_booking

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED, summary="Create a booking")
def create(
    body: BookingCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    booking = create_booking(
        db=db,
        user_id=current_user.id,
        centre_id=body.centre_id,
        test_id=body.test_id,
        appointment_at=body.appointment_at,
    )
    return booking


@router.get("", response_model=PaginatedResponse[BookingResponse], summary="List your bookings")
def list_bookings(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = db.query(Booking).filter(Booking.user_id == current_user.id)
    total = query.count()
    items = query.order_by(Booking.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/{booking_id}", response_model=BookingResponse, summary="Get a booking")
def get_booking(
    booking_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingResponse, summary="Cancel a booking")
def cancel(
    booking_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return cancel_booking(db=db, booking_id=booking_id, user_id=current_user.id)
