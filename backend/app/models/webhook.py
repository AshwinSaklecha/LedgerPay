from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class WebhookEvent:
    id: UUID
    payment_intent_id: UUID
    merchant_id: UUID
    event_type: str
    payload: dict
    status: str          # PENDING | DELIVERED | FAILED
    attempt_count: int
    next_attempt_at: datetime
    delivered_at: datetime | None
    created_at: datetime
