from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentIntentCreateRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in cents (e.g. 1000 = $10.00)")
    currency: str = Field(default="usd", pattern=r"^[a-z]{3}$")


class PaymentIntentResponse(BaseModel):
    id: UUID
    merchant_id: UUID
    amount: int
    currency: str
    status: str
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
