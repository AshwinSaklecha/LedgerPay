import redis

from app.core.config import settings

_client: redis.Redis | None = None


def init_redis() -> None:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)


def close_redis() -> None:
    global _client
    if _client:
        _client.close()
        _client = None


def get_redis() -> redis.Redis:
    assert _client is not None, "Redis client not initialized"
    return _client
