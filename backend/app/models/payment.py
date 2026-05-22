from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class PaymentIntent:
    id: UUID
    merchant_id: UUID
    amount: int
    currency: str
    status: str
    idempotency_key: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
