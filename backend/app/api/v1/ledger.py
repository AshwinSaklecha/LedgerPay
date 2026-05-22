from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_merchant
from app.core.database import get_conn
from app.models.merchant import Merchant
from app.schemas.ledger import BalanceResponse, LedgerEntryResponse
from app.services.ledger_service import get_balance, list_entries

router = APIRouter(prefix="/ledger", tags=["Ledger"])


@router.get("/balance", response_model=BalanceResponse)
def get_merchant_balance(
    currency: str = Query(default="usd", pattern=r"^[a-z]{3}$"),
    current: Merchant = Depends(get_current_merchant),
):
    """
    Return the authenticated merchant's balance.
    balance = SUM(CREDITs) - SUM(DEBITs) across all succeeded payments.
    """
    with get_conn() as conn:
        result = get_balance(conn, current.id, currency)
    return BalanceResponse(**result)


@router.get("/entries", response_model=list[LedgerEntryResponse])
def get_ledger_entries(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current: Merchant = Depends(get_current_merchant),
):
    """List all ledger entries for the authenticated merchant."""
    with get_conn() as conn:
        entries = list_entries(conn, current.id, limit, offset)
    return [
        LedgerEntryResponse(
            id=e.id,
            payment_intent_id=e.payment_intent_id,
            entry_type=e.entry_type,
            account_type=e.account_type,
            amount=e.amount,
            currency=e.currency,
            created_at=e.created_at,
        )
        for e in entries
    ]
