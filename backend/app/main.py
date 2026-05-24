import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import close_pool, init_pool
from app.core.logging import RequestIDMiddleware, setup_logging
from app.core.redis_client import close_redis, init_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    logger.info("Starting LedgerPay - environment=%s", settings.environment)
    init_pool()
    init_redis()
    yield
    # Skip teardown in tests — the session fixture owns the lifecycle
    if settings.environment != "test":
        close_pool()
        close_redis()
        logger.info("LedgerPay shut down cleanly")


app = FastAPI(
    title="LedgerPay",
    description=(
        "A Stripe-like idempotent payments backend.\n\n"
        "## Authentication\n"
        "All payment and ledger endpoints require an `X-API-Key` header.\n"
        "Obtain your key by registering a merchant — it is shown **once** and never stored in plaintext.\n\n"
        "## Idempotency\n"
        "Supply an `Idempotency-Key` header on `POST` requests to safely retry "
        "failed network calls without risk of duplicate charges. "
        "Responses are cached in Redis for 24 hours.\n\n"
        "## Webhook Signatures\n"
        "Every webhook delivery includes `X-LedgerPay-Signature: sha256=<hmac>`. "
        "Verify it with `HMAC-SHA256(signing_key, payload)` to confirm the request "
        "came from LedgerPay."
    ),
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "System", "description": "Health check"},
        {"name": "Merchants", "description": "Register merchants and manage API keys"},
        {
            "name": "Payments",
            "description": (
                "Create and confirm payment intents. "
                "Confirmation triggers the mock bank, acquires a row-level lock (`SELECT FOR UPDATE`), "
                "writes double-entry ledger entries, and enqueues a webhook event — all in one transaction."
            ),
        },
        {
            "name": "Ledger",
            "description": (
                "Double-entry accounting ledger. "
                "Every succeeded payment creates a DEBIT (customer) and CREDIT (merchant) entry atomically. "
                "The invariant `SUM(DEBITs) == SUM(CREDITs)` always holds."
            ),
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url] if settings.frontend_url else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "version": "1.0.0"}


from app.api.v1 import ledger, merchants, payments
app.include_router(merchants.router, prefix="/v1")
app.include_router(payments.router, prefix="/v1")
app.include_router(ledger.router, prefix="/v1")

# Phase 5+: webhook worker runs as a separate process
