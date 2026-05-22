import logging
from uuid import UUID

import psycopg2.extensions

from app.core.security import generate_api_key, hash_api_key
from app.models.merchant import Merchant

logger = logging.getLogger(__name__)


class DuplicateEmailError(Exception):
    pass


def register_merchant(
    conn: psycopg2.extensions.connection,
    name: str,
    email: str,
    webhook_url: str | None,
) -> tuple[Merchant, str]:
    """
    Create a new merchant. Returns (Merchant, plaintext_api_key).
    The plaintext key is shown to the caller once and never stored.
    """
    plaintext_key = generate_api_key()
    hashed = hash_api_key(plaintext_key)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO merchants (name, email, hashed_api_key, webhook_url)
                VALUES (%s, %s, %s, %s)
                RETURNING id, name, email, hashed_api_key, webhook_url, is_active, created_at
                """,
                (name, email, hashed, webhook_url),
            )
            row = cur.fetchone()
    except Exception as exc:
        if "uq_merchants_email" in str(exc):
            raise DuplicateEmailError(f"Email already registered: {email}") from exc
        raise

    merchant = _row_to_merchant(row)
    logger.info("Merchant registered id=%s email=%s", merchant.id, merchant.email)
    return merchant, plaintext_key


def get_merchant_by_id(
    conn: psycopg2.extensions.connection,
    merchant_id: UUID,
) -> Merchant | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, email, hashed_api_key, webhook_url, is_active, created_at
            FROM merchants WHERE id = %s
            """,
            (str(merchant_id),),
        )
        row = cur.fetchone()
    return _row_to_merchant(row) if row else None


def get_merchant_by_hashed_key(
    conn: psycopg2.extensions.connection,
    hashed_key: str,
) -> Merchant | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, email, hashed_api_key, webhook_url, is_active, created_at
            FROM merchants WHERE hashed_api_key = %s AND is_active = true
            """,
            (hashed_key,),
        )
        row = cur.fetchone()
    return _row_to_merchant(row) if row else None


def _row_to_merchant(row: dict) -> Merchant:
    return Merchant(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        hashed_api_key=row["hashed_api_key"],
        webhook_url=row["webhook_url"],
        is_active=row["is_active"],
        created_at=row["created_at"],
    )
