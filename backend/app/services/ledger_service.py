"""
Double-entry ledger service.

Every successful payment creates exactly two rows atomically:
  DEBIT  | CUSTOMER account  (money leaving the customer)
  CREDIT | MERCHANT account  (money arriving at the merchant)

Invariant that must always hold:
  SUM(amount WHERE entry_type = 'DEBIT') == SUM(amount WHERE entry_type = 'CREDIT')

This is enforced by always writing both entries in the same DB transaction
via write_double_entry(), which is called as an on_success_hook inside
the payment confirm transaction.
"""
import logging
from uuid import UUID

import psycopg2.extensions

from app.models.ledger import LedgerEntry
from app.models.payment import PaymentIntent

logger = logging.getLogger(__name__)

_INSERT_SQL = """
    INSERT INTO ledger_entries
        (payment_intent_id, merchant_id, entry_type, account_type, amount, currency)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id, payment_intent_id, merchant_id, entry_type, account_type, amount, currency, created_at
"""


def write_double_entry(
    conn: psycopg2.extensions.connection,
    intent: PaymentIntent,
) -> tuple[LedgerEntry, LedgerEntry]:
    """
    Write a DEBIT (customer) and CREDIT (merchant) entry for a succeeded payment.
    Must be called inside an already-open transaction (the same one that
    updated payment status to SUCCEEDED).
    """
    with conn.cursor() as cur:
        cur.execute(
            _INSERT_SQL,
            (str(intent.id), str(intent.merchant_id), "DEBIT", "CUSTOMER", intent.amount, intent.currency),
        )
        debit = _row_to_entry(cur.fetchone())

        cur.execute(
            _INSERT_SQL,
            (str(intent.id), str(intent.merchant_id), "CREDIT", "MERCHANT", intent.amount, intent.currency),
        )
        credit = _row_to_entry(cur.fetchone())

    logger.info(
        "Ledger double-entry written payment_id=%s amount=%d currency=%s",
        intent.id, intent.amount, intent.currency,
    )
    return debit, credit


def get_balance(
    conn: psycopg2.extensions.connection,
    merchant_id: UUID,
    currency: str = "usd",
) -> dict:
    """
    Return the merchant's balance.
    balance = SUM(CREDIT) - SUM(DEBIT) for this merchant.
    For a payment processor, credits (received funds) always >= debits,
    so balance is always >= 0 for a healthy ledger.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COALESCE(
                    SUM(amount) FILTER (WHERE entry_type = 'CREDIT' AND account_type = 'MERCHANT'),
                    0
                ) AS total_received
            FROM ledger_entries
            WHERE merchant_id = %s AND currency = %s
            """,
            (str(merchant_id), currency),
        )
        row = cur.fetchone()

    total_received = row["total_received"]
    return {
        "merchant_id": merchant_id,
        "balance": total_received,
        "currency": currency,
        "total_received": total_received,
    }


def list_entries(
    conn: psycopg2.extensions.connection,
    merchant_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[LedgerEntry]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, payment_intent_id, merchant_id, entry_type, account_type, amount, currency, created_at
            FROM ledger_entries
            WHERE merchant_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (str(merchant_id), limit, offset),
        )
        return [_row_to_entry(r) for r in cur.fetchall()]


def _row_to_entry(row: dict) -> LedgerEntry:
    return LedgerEntry(
        id=row["id"],
        payment_intent_id=row["payment_intent_id"],
        merchant_id=row["merchant_id"],
        entry_type=row["entry_type"],
        account_type=row["account_type"],
        amount=row["amount"],
        currency=row["currency"],
        created_at=row["created_at"],
    )
