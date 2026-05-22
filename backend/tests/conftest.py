import os
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

# Load backend/.env so tests run without needing manually exported env vars.
# os.environ.setdefault() means existing shell exports always win.
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Override environment to test mode
os.environ["ENVIRONMENT"] = "test"
# Use a safe test secret (not the production one from .env)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

from app.core.database import close_pool, init_pool  # noqa: E402
from app.core.redis_client import get_redis, init_redis  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def db_pool():
    init_pool()
    init_redis()
    yield
    close_pool()


@pytest.fixture()
def client(db_pool):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def raw_conn():
    """Direct psycopg2 connection for test setup/teardown."""
    conn = psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def clean_db(raw_conn, db_pool):
    """Truncate all tables and flush Redis idempotency keys before each test."""
    with raw_conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE merchants CASCADE")
    get_redis().flushdb()
    yield
