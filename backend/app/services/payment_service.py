"""
Payment intent business logic.

Key design decisions:
  - SELECT FOR UPDATE prevents two concurrent confirm requests from both
    calling the mock bank on the same payment intent.
  - The entire confirm flow (lock → PROCESSING → bank call → final status)
    runs inside a single DB transaction. If the process crashes mid-way,
    PostgreSQL rolls back and the intent stays at CREATED so the client
    can safely retry.
  - Ledger writes and webhook event insertion happen in the same transaction
    (added in Phases 4 and 5 via the on_success_hooks list).
"""
import logging
from uuid import UUID

import psycopg2.extensions

from app.models.payment import PaymentIntent
from app.services import mock_bank
from app.services.mock_bank import BankOutcome

logger = logging.getLogger(__name__)


class PaymentNotFoundError(Exception):
    pass


class PaymentConflictError(Exception):
    """Raised when confirm is attempted on a payment not in CREATED state."""
    pass


def create_payment_intent(
    conn: psycopg2.extensions.connection,
    merchant_id: UUID,
    amount: int,
    currency: str,
    idempotency_key: str | None,
) -> PaymentIntent:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payment_intents (merchant_id, amount, currency, idempotency_key)
                VALUES (%s, %s, %s, %s)
                RETURNING id, merchant_id, amount, currency, status,
                          idempotency_key, failure_reason, created_at, updated_at
                """,
                (str(merchant_id), amount, currency, idempotency_key),
            )
            row = cur.fetchone()
    except Exception as exc:
        # Two concurrent requests with the same brand-new idempotency key both
        # pass the Redis cache check (empty), then race to INSERT. The loser
        # hits the UNIQUE(merchant_id, idempotency_key) constraint. Recover by
        # fetching the winner's row — same outcome as a cache hit.
        if idempotency_key and "uq_payment_intent_idempotency" in str(exc):
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, merchant_id, amount, currency, status,
                           idempotency_key, failure_reason, created_at, updated_at
                    FROM payment_intents
                    WHERE merchant_id = %s AND idempotency_key = %s
                    """,
                    (str(merchant_id), idempotency_key),
                )
                row = cur.fetchone()
            if not row:
                raise
        else:
            raise

    intent = _row_to_intent(row)
    logger.info("PaymentIntent created id=%s merchant=%s amount=%d", intent.id, merchant_id, amount)
    return intent


def confirm_payment_intent(
    conn: psycopg2.extensions.connection,
    intent_id: UUID,
    merchant_id: UUID,
    on_success_hooks: list | None = None,
) -> PaymentIntent:
    """
    Confirm a payment intent. Steps:
      1. SELECT FOR UPDATE — acquire row lock, preventing concurrent confirms
      2. Validate state is CREATED
      3. Set status = PROCESSING
      4. Call mock bank
      5. Set final status (SUCCEEDED / FAILED / TIMED_OUT)
      6. Run on_success_hooks inside the same transaction (ledger + webhook)
      7. Commit (handled by get_conn() context manager)
    """
    with conn.cursor() as cur:
        # Step 1: Lock the row — concurrent request will block here until we commit
        cur.execute(
            """
            SELECT id, merchant_id, amount, currency, status,
                   idempotency_key, failure_reason, created_at, updated_at
            FROM payment_intents
            WHERE id = %s AND merchant_id = %s
            FOR UPDATE
            """,
            (str(intent_id), str(merchant_id)),
        )
        row = cur.fetchone()

    if not row:
        raise PaymentNotFoundError(f"Payment intent {intent_id} not found")

    intent = _row_to_intent(row)

    # Reject if not in a confirmable state.
    # Idempotency for re-confirms is handled at the API layer via Redis cache
    # (Idempotency-Key header), not silently here.
    if intent.status != "CREATED":
        raise PaymentConflictError(
            f"Cannot confirm payment in state '{intent.status}'"
        )

    # Step 3: Mark as PROCESSING — visible to any other request that unlocks after us
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE payment_intents SET status = 'PROCESSING', updated_at = NOW() WHERE id = %s",
            (str(intent_id),),
        )

    # Step 4: Call mock bank (still inside the open transaction)
    bank_result = mock_bank.charge(intent.amount)

    # Step 5: Map bank outcome to payment status
    if bank_result.outcome == BankOutcome.SUCCESS:
        new_status = "SUCCEEDED"
    elif bank_result.outcome == BankOutcome.DECLINE:
        new_status = "FAILED"
    else:  # TIMEOUT
        new_status = "TIMED_OUT"

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE payment_intents
            SET status = %s, failure_reason = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id, merchant_id, amount, currency, status,
                      idempotency_key, failure_reason, created_at, updated_at
            """,
            (new_status, bank_result.failure_reason, str(intent_id)),
        )
        updated_row = cur.fetchone()

    updated_intent = _row_to_intent(updated_row)

    # Step 6: Run success hooks (ledger + webhook) inside the same transaction
    if new_status == "SUCCEEDED" and on_success_hooks:
        for hook in on_success_hooks:
            hook(conn, updated_intent)

    logger.info(
        "PaymentIntent confirmed id=%s status=%s amount=%d",
        intent_id, new_status, intent.amount,
    )
    return updated_intent


def get_payment_intent(
    conn: psycopg2.extensions.connection,
    intent_id: UUID,
    merchant_id: UUID,
) -> PaymentIntent | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, merchant_id, amount, currency, status,
                   idempotency_key, failure_reason, created_at, updated_at
            FROM payment_intents
            WHERE id = %s AND merchant_id = %s
            """,
            (str(intent_id), str(merchant_id)),
        )
        row = cur.fetchone()
    return _row_to_intent(row) if row else None


def list_payment_intents(
    conn: psycopg2.extensions.connection,
    merchant_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[PaymentIntent]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, merchant_id, amount, currency, status,
                   idempotency_key, failure_reason, created_at, updated_at
            FROM payment_intents
            WHERE merchant_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (str(merchant_id), limit, offset),
        )
        rows = cur.fetchall()
    return [_row_to_intent(r) for r in rows]


def _row_to_intent(row: dict) -> PaymentIntent:
    return PaymentIntent(
        id=row["id"],
        merchant_id=row["merchant_id"],
        amount=row["amount"],
        currency=row["currency"],
        status=row["status"],
        idempotency_key=row["idempotency_key"],
        failure_reason=row["failure_reason"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
