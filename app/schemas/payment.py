from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class PaymentCreate(BaseModel):
    booking_id: int
    simulate_result: Literal["SUCCESS", "FAILED"]


class PaymentResponse(BaseModel):
    id: int
    booking_id: int
    provider_payment_id: str | None
    amount: Decimal
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookPayload(BaseModel):
    event_id: str
    event_type: Literal["payment.success", "payment.failed"]
    payment_id: int
    status: Literal["SUCCESS", "FAILED"]
