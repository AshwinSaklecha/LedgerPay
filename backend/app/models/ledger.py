from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class LedgerEntry:
    id: UUID
    payment_intent_id: UUID
    merchant_id: UUID
    entry_type: str   # DEBIT | CREDIT
    account_type: str  # CUSTOMER | MERCHANT
    amount: int
    currency: str
    created_at: datetime
