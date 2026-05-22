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
  │   PostgreSQL 18    │      │      Redis 7           │
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
|-----------|------------|-----------------|
| 0         | SUCCEEDED  | 1000, 2000, 5000 |
| 1         | FAILED     | 1001, 2001       |
| 2         | TIMED_OUT  | 1002, 2002       |
| other     | SUCCEEDED  | 1003, 1005, 1009 |

---

## Tech Stack

| Layer       | Technology           |
|-------------|----------------------|
| API         | FastAPI + Uvicorn    |
| Database    | PostgreSQL 18        |
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
# Edit .env with your PostgreSQL credentials

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

## Tests

```bash
cd backend
pytest tests/ -v
```

**52 tests** covering:
- Merchant registration and API key authentication
- Payment intent create / confirm (success, decline, timeout)
- Idempotency key deduplication
- Concurrent confirm requests (SELECT FOR UPDATE)
- Double-entry ledger entries and balance
- Ledger invariant under concurrent load (20 threads)
- Webhook outbox atomicity (event created in same transaction as payment)
- HMAC signature generation and verification
- Webhook retry backoff and max-attempts handling
- Full end-to-end flow (12-step integration test)
