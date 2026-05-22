"""
Webhook service — transactional outbox pattern.

insert_outbox_event() is called as an on_success_hook inside the payment
confirm transaction. This guarantees: if the payment succeeds, the webhook
event row exists. If the transaction rolls back, neither the payment status
update nor the webhook event are written. There is no gap where a payment
succeeds but no webhook is ever sent.

Signing:
  Each delivery includes an X-LedgerPay-Signature header:
    sha256=HMAC-SHA256(signing_key, payload_json)

  signing_key = HMAC-SHA256(SECRET_KEY, merchant_id)
  This is deterministic from config — no extra DB column needed.
  Merchants verify the signature on their end to confirm the request
  came from LedgerPay and was not tampered with.
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import psycopg2.extensions

from app.core.config import settings
from app.models.payment import PaymentIntent
from app.models.webhook import WebhookEvent

logger = logging.getLogger(__name__)


def _derive_signing_key(merchant_id: UUID) -> bytes:
    """Derive a per-merchant HMAC signing key from the global secret."""
    return hmac.new(
        settings.secret_key.encode(),
        str(merchant_id).encode(),
        hashlib.sha256,
    ).digest()


def sign_payload(merchant_id: UUID, payload_json: str) -> str:
    """Return the hex HMAC-SHA256 signature for a webhook payload."""
    key = _derive_signing_key(merchant_id)
    signature = hmac.new(key, payload_json.encode(), hashlib.sha256).hexdigest()
    return f"sha256={signature}"


def verify_signature(merchant_id: UUID, payload_json: str, header_value: str) -> bool:
    """Verify an incoming X-LedgerPay-Signature header. Used by merchants."""
    expected = sign_payload(merchant_id, payload_json)
    return hmac.compare_digest(expected, header_value)


def insert_outbox_event(
    conn: psycopg2.extensions.connection,
    intent: PaymentIntent,
) -> WebhookEvent:
    """
    Insert a webhook event into the outbox table.
    Must be called inside an already-open transaction (same one that
    updated payment status to SUCCEEDED and wrote ledger entries).
    """
    payload = {
        "event_type": "payment_intent.succeeded",
        "payment_intent_id": str(intent.id),
        "merchant_id": str(intent.merchant_id),
        "amount": intent.amount,
        "currency": intent.currency,
        "status": intent.status,
    }

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO webhook_events
                (payment_intent_id, merchant_id, event_type, payload)
            VALUES (%s, %s, %s, %s)
            RETURNING id, payment_intent_id, merchant_id, event_type, payload,
                      status, attempt_count, next_attempt_at, delivered_at, created_at
            """,
            (
                str(intent.id),
                str(intent.merchant_id),
                "payment_intent.succeeded",
                json.dumps(payload),
            ),
        )
        row = cur.fetchone()

    event = _row_to_event(row)
    logger.info(
        "Webhook outbox event inserted id=%s payment_id=%s",
        event.id, intent.id,
    )
    return event


def _row_to_event(row: dict) -> WebhookEvent:
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return WebhookEvent(
        id=row["id"],
        payment_intent_id=row["payment_intent_id"],
        merchant_id=row["merchant_id"],
        event_type=row["event_type"],
        payload=payload,
        status=row["status"],
        attempt_count=row["attempt_count"],
        next_attempt_at=row["next_attempt_at"],
        delivered_at=row["delivered_at"],
        created_at=row["created_at"],
    )
