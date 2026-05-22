"""FastAPI dependency for API key authentication."""
import logging

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.database import get_conn
from app.core.security import hash_api_key
from app.models.merchant import Merchant
from app.services.merchant_service import get_merchant_by_hashed_key

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_current_merchant(
    raw_key: str | None = Security(_api_key_header),
) -> Merchant:
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    hashed = hash_api_key(raw_key)
    with get_conn() as conn:
        merchant = get_merchant_by_hashed_key(conn, hashed)

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return merchant
