from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_webhook_secret
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentResponse, WebhookPayload
from app.services.payment import process_payment, process_webhook

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED, summary="Simulate a payment")
def create_payment(
    body: PaymentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return process_payment(
        db=db,
        booking_id=body.booking_id,
        user_id=current_user.id,
        simulate_result=body.simulate_result,
    )


@router.post(
    "/webhook",
    summary="Payment provider webhook",
    description="Receives payment status updates. Requires X-Webhook-Secret header.",
    dependencies=[Depends(verify_webhook_secret)],
)
def payment_webhook(
    body: WebhookPayload,
    db: Annotated[Session, Depends(get_db)],
):
    return process_webhook(
        db=db,
        event_id=body.event_id,
        event_type=body.event_type,
        payment_id=body.payment_id,
        event_status=body.status,
    )
