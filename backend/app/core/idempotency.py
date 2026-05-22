"""
Idempotency key support backed by Redis.

Cache key format: idem:{scope}:{merchant_id}:{idempotency_key}
TTL: 24 hours

Usage:
  - On first request: process normally, then call cache_response()
  - On duplicate request: get_cached_response() returns the prior JSON → return it directly
"""
import json
import logging
from uuid import UUID

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

_TTL_SECONDS = 86_400  # 24 hours


def _build_key(scope: str, merchant_id: UUID, idempotency_key: str) -> str:
    return f"idem:{scope}:{merchant_id}:{idempotency_key}"


def get_cached_response(scope: str, merchant_id: UUID, idempotency_key: str) -> dict | None:
    """Return cached response dict if the key was seen before, else None."""
    key = _build_key(scope, merchant_id, idempotency_key)
    raw = get_redis().get(key)
    if raw:
        logger.info("Idempotency cache HIT scope=%s key=%s", scope, idempotency_key)
        return json.loads(raw)
    return None


def cache_response(scope: str, merchant_id: UUID, idempotency_key: str, response: dict) -> None:
    """Store a response in the idempotency cache."""
    key = _build_key(scope, merchant_id, idempotency_key)
    get_redis().setex(key, _TTL_SECONDS, json.dumps(response, default=str))
    logger.info("Idempotency cache SET scope=%s key=%s ttl=%ds", scope, idempotency_key, _TTL_SECONDS)
