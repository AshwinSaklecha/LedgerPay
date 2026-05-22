import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.core.auth import get_current_merchant
from app.core.database import get_conn
from app.core.idempotency import cache_response, get_cached_response
from app.models.merchant import Merchant
from app.schemas.payment import PaymentIntentCreateRequest, PaymentIntentResponse
from app.services.ledger_service import write_double_entry
from app.services.webhook_service import insert_outbox_event
from app.services.payment_service import (
    PaymentConflictError,
    PaymentNotFoundError,
    confirm_payment_intent,
    create_payment_intent,
    get_payment_intent,
    list_payment_intents,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payment-intents", tags=["Payments"])


def _intent_to_dict(intent) -> dict:
    return PaymentIntentResponse(
        id=intent.id,
        merchant_id=intent.merchant_id,
        amount=intent.amount,
        currency=intent.currency,
        status=intent.status,
        failure_reason=intent.failure_reason,
        created_at=intent.created_at,
        updated_at=intent.updated_at,
    ).model_dump()


@router.post("", response_model=PaymentIntentResponse, status_code=status.HTTP_201_CREATED)
def create_intent(
    body: PaymentIntentCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current: Merchant = Depends(get_current_merchant),
):
    """
    Create a payment intent. Optionally supply an Idempotency-Key header —
    duplicate requests with the same key return the original response from cache.
    """
    if idempotency_key:
        cached = get_cached_response("create_intent", current.id, idempotency_key)
        if cached:
            return cached

    with get_conn() as conn:
        intent = create_payment_intent(
            conn, current.id, body.amount, body.currency, idempotency_key
        )

    response = _intent_to_dict(intent)

    if idempotency_key:
        cache_response("create_intent", current.id, idempotency_key, response)

    return response


@router.post("/{intent_id}/confirm", response_model=PaymentIntentResponse)
def confirm_intent(
    intent_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current: Merchant = Depends(get_current_merchant),
):
    """
    Confirm a payment intent. Triggers the mock bank.

    SELECT FOR UPDATE is used to prevent two concurrent confirms from both
    calling the bank on the same payment — the second request blocks until
    the first commits, then sees the updated status and returns immediately.

    Supply Idempotency-Key to safely retry a failed network request without
    risk of double-charging.
    """
    if idempotency_key:
        cached = get_cached_response("confirm_intent", current.id, idempotency_key)
        if cached:
            return cached

    try:
        with get_conn() as conn:
            intent = confirm_payment_intent(
                conn,
                intent_id=intent_id,
                merchant_id=current.id,
                on_success_hooks=[
                    write_double_entry,    # ledger entries in same transaction
                    insert_outbox_event,   # webhook outbox in same transaction
                ],
            )
    except PaymentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment intent not found")
    except PaymentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    response = _intent_to_dict(intent)

    if idempotency_key:
        cache_response("confirm_intent", current.id, idempotency_key, response)

    return response


@router.get("/{intent_id}", response_model=PaymentIntentResponse)
def get_intent(
    intent_id: UUID,
    current: Merchant = Depends(get_current_merchant),
):
    with get_conn() as conn:
        intent = get_payment_intent(conn, intent_id, current.id)

    if not intent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment intent not found")

    return _intent_to_dict(intent)


@router.get("", response_model=list[PaymentIntentResponse])
def list_intents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current: Merchant = Depends(get_current_merchant),
):
    with get_conn() as conn:
        intents = list_payment_intents(conn, current.id, limit, offset)
    return [_intent_to_dict(i) for i in intents]
