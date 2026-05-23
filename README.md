# LedgerPay

A Stripe-like idempotent payments backend built to demonstrate payment state machines, database transactions, row-level locking, double-entry accounting, and reliable webhook delivery.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client / Merchant                    │
└───────────────────────────┬─────────────────────────────────┘
                            │  HTTPS + X-API-Key header
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI (uvicorn)                       │
│                                                             │
│   POST /v1/merchants          ← register, get API key       │
│   POST /v1/payment-intents    ← create payment intent       │
│   POST /v1/payment-intents/:id/confirm  ← trigger bank      │
│   GET  /v1/ledger/balance     ← merchant balance            │
│   GET  /v1/ledger/entries     ← ledger rows                 │
│   GET  /health                                              │
└──────────────┬──────────────────────────┬───────────────────┘
               │                          │
               ▼                          ▼
  ┌────────────────────┐      ┌───────────────────────┐
  │   PostgreSQL       │      │      Redis 7           │
  │                    │      │                        │
  │  merchants         │      │  Idempotency cache     │
  │  payment_intents   │      │  (24h TTL, per-key)    │
  │  ledger_entries    │      └───────────────────────┘
  │  webhook_events    │
  └────────────────────┘
               │
               ▼ (separate process)
┌─────────────────────────────────────────────────────────────┐
│                    Webhook Worker                           │
│  Polls webhook_events every 5s → POST to merchant URL      │
│  Exponential backoff: 10s → 30s → 2m → 10m → give up      │
│  Signs each payload with HMAC-SHA256                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Payment State Machine

```
                    ┌─────────────┐
                    │   CREATED   │  ← POST /v1/payment-intents
                    └──────┬──────┘
                           │ POST /v1/payment-intents/:id/confirm
                           │ (SELECT FOR UPDATE acquired here)
                           ▼
                    ┌─────────────┐
                    │ PROCESSING  │
                    └──────┬──────┘
                           │ mock bank called
               ┌───────────┼───────────┐
               ▼           ▼           ▼
         ┌──────────┐ ┌─────────┐ ┌──────────┐
         │SUCCEEDED │ │ FAILED  │ │TIMED_OUT │
         └──────────┘ └─────────┘ └──────────┘
```

On `SUCCEEDED`, inside the **same database transaction**:
1. Two ledger entries are written (DEBIT customer / CREDIT merchant)
2. A `webhook_events` outbox row is inserted

This guarantees atomicity — no partial state is ever possible.

---

## Key Design Decisions

### Idempotency Keys
The client sends an `Idempotency-Key: <uuid>` header. The response is cached in Redis with a 24-hour TTL, keyed by `merchant_id + key`. Duplicate requests return the cached response immediately — no DB write, no bank call. This prevents double charges on network retries.

There is also a DB-level `UNIQUE(merchant_id, idempotency_key)` constraint as a second line of defence: if two concurrent requests with the same brand-new key both pass the Redis cache check simultaneously, the database constraint rejects the duplicate insert and the API recovers gracefully by fetching the existing row.

### SELECT FOR UPDATE (Row Locking)
When confirming a payment, the service acquires a row-level lock on the `payment_intents` row before reading its status. If two concurrent confirm requests arrive simultaneously, one blocks at the lock and waits. When it unblocks, it reads `status = PROCESSING` or `SUCCEEDED` and returns a 409 — the bank is never called twice.

### Double-Entry Ledger
Every succeeded payment atomically writes two rows:
```
DEBIT  | CUSTOMER account | amount   (money leaving customer)
CREDIT | MERCHANT account | amount   (money arriving at merchant)
```
The invariant `SUM(all DEBITs) == SUM(all CREDITs)` is enforced by always writing both entries in the same transaction. A test verifies this invariant after 20 concurrent payments.

### Transactional Outbox Pattern
The `webhook_events` row is inserted in the **same transaction** as the payment status update and ledger writes. If the API process crashes after commit, the webhook event exists in the DB and the worker will deliver it. If the process crashes before commit, none of it is written. There is no window where a payment succeeds but no webhook is ever sent.

### Webhook HMAC Signing
Each webhook POST includes `X-LedgerPay-Signature: sha256=<hmac>`. The signing key is derived as `HMAC-SHA256(SECRET_KEY, merchant_id)` — deterministic from config, no extra DB column. Merchants verify the signature to confirm the request came from LedgerPay and was not tampered with.

### API Key Design
Keys are generated as `lp_<32 random bytes hex>` using `secrets.token_hex`. The plaintext is shown once in the registration response and never stored. Only `SHA-256(key)` is persisted. Auth middleware hashes the incoming key and does a constant-time compare.

---

## Mock Bank Behavior

Deterministic based on payment amount (last digit):

| Last digit | Outcome    | Example amounts |
|-----------|------------|--------------------|
| 1         | FAILED     | 1001, 2001         |
| 2         | TIMED_OUT  | 1002, 2002         |
| other     | SUCCEEDED  | 1000, 1003, 5000   |

This makes tests fully deterministic without any mocking of the bank.

---

## Tech Stack

| Layer       | Technology           |
|-------------|----------------------|
| API         | FastAPI + Uvicorn    |
| Database    | PostgreSQL           |
| Migrations  | Alembic              |
| Cache       | Redis 7              |
| DB Driver   | psycopg2-binary      |
| Config      | pydantic-settings    |
| Tests       | pytest + httpx       |

---

## Running Locally

**Prerequisites:** Python 3.13, PostgreSQL, Redis

```bash
# 1. Clone and enter backend
cd backend

# 2. Create virtualenv and install
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 3. Copy env and configure
copy .env.example .env
# Edit .env with your PostgreSQL credentials and a strong SECRET_KEY

# 4. Run migrations
alembic upgrade head

# 5. Start API server
uvicorn app.main:app --reload --port 8000

# 6. Start webhook worker (separate terminal)
python -m app.worker.webhook_worker
```

API docs: http://localhost:8000/docs

---

## API Quick Reference

### Register a merchant
```bash
curl -X POST http://localhost:8000/v1/merchants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "email": "acme@example.com",
    "webhook_url": "https://acme.example.com/webhooks"
  }'
```

Response (save `api_key` — shown once):
```json
{
  "id": "...",
  "name": "Acme Corp",
  "email": "acme@example.com",
  "api_key": "lp_abc123...",
  "created_at": "..."
}
```

### Create a payment intent
```bash
curl -X POST http://localhost:8000/v1/payment-intents \
  -H "X-API-Key: lp_abc123..." \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"amount": 5000, "currency": "usd"}'
```

### Confirm the payment
```bash
curl -X POST http://localhost:8000/v1/payment-intents/<intent_id>/confirm \
  -H "X-API-Key: lp_abc123..." \
  -H "Idempotency-Key: $(uuidgen)"
```

### Check balance
```bash
curl http://localhost:8000/v1/ledger/balance \
  -H "X-API-Key: lp_abc123..."
```

---

## Deployment

The API and webhook worker are deployed as a single Render web service using [`backend/start.sh`](file:///d:/LedgerPay/backend/start.sh):

```bash
python -m app.worker.webhook_worker &   # runs in background
exec uvicorn app.main:app ...           # Render watches this process
```

**Why:** Render's free tier only includes Web Services, not Background Workers. Running both processes in one container is a cost-free workaround.

**The tradeoff:** Both the API and the worker share the same PostgreSQL connection pool. Under high concurrent API load, this reduces the connections available to the worker. In a production deployment, the webhook worker would run as a separate service with its own isolated pool.

This is the same approach used in the companion project [VortexQueue](https://github.com/AshwinSaklecha/VortexQueue), where the API, worker, and janitor all run in a single container.

---

## Tests

```bash
cd backend
pytest tests/ -v
```

**52 tests** covering:
- Merchant registration and API key authentication
- Payment intent create / confirm (success, decline, timeout)
- Idempotency key deduplication (Redis cache + DB constraint)
- Concurrent confirm requests (SELECT FOR UPDATE prevents double-charge)
- Double-entry ledger entries and balance
- Ledger invariant under concurrent load (20 threads)
- Webhook outbox atomicity (event created in same transaction as payment)
- HMAC signature generation and verification
- Webhook retry backoff (exponential delays with ±20% jitter) and max-attempts handling
- Full end-to-end flow (12-step integration test)

---

## What This Project Does Not Do

- No real card processing — the mock bank is deterministic and synchronous
- No refunds, chargebacks, or multi-currency
- No rate limiting on the merchant registration endpoint
- The mock bank does not simulate actual network latency for TIMED_OUT — it returns the timeout outcome immediately
