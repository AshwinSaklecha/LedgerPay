from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LedgerEntryResponse(BaseModel):
    id: UUID
    payment_intent_id: UUID
    entry_type: str
    account_type: str
    amount: int
    currency: str
    created_at: datetime


class BalanceResponse(BaseModel):
    merchant_id: UUID
    balance: int        # net credit - debit in cents
    currency: str
    total_received: int  # sum of all CREDIT entries
