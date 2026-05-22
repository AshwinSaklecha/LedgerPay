import os

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

# Point to the test database (same DB, tests clean up after themselves)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:M%40haveer2004@localhost:5432/ledgerpay",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENVIRONMENT", "test")

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
