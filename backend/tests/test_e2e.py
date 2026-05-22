"""
End-to-end integration test — full payment lifecycle.

This single test walks through the entire system exactly as a real merchant
would use it, verifying every layer works together:

  1. Merchant registers → receives API key
  2. Merchant authenticates → profile returned correctly
  3. Merchant creates a payment intent (with idempotency key)
  4. Duplicate create request with same idempotency key → same intent returned
  5. Merchant confirms the payment intent → SUCCEEDED
  6. Ledger: exactly 2 entries written (DEBIT customer / CREDIT merchant)
  7. Ledger: merchant balance equals payment amount
  8. Ledger: global invariant holds (SUM DEBITs == SUM CREDITs)
  9. Webhook: outbox event in PENDING state with correct payload
  10. Webhook: event payload is signed correctly (HMAC verification)
  11. Payment: cannot confirm the same intent twice (409)
  12. Payment: second merchant cannot access first merchant's data
"""
import json
from uuid import uuid4

import pytest

from app.services.webhook_service import verify_signature


class TestFullPaymentLifecycle:
    def test_complete_flow(self, client, raw_conn):
        # ── Step 1: Register merchant ──────────────────────────────────────
        reg = client.post(
            "/v1/merchants",
            json={
                "name": "Acme Payments",
                "email": "acme@e2e.com",
                "webhook_url": "https://acme.example.com/webhooks",
            },
        )
        assert reg.status_code == 201
        reg_data = reg.json()
        api_key = reg_data["api_key"]
        merchant_id = reg_data["id"]
        assert api_key.startswith("lp_")

        auth = {"X-API-Key": api_key}

        # ── Step 2: Authenticate ───────────────────────────────────────────
        me = client.get("/v1/merchants/me", headers=auth)
        assert me.status_code == 200
        assert me.json()["id"] == merchant_id
        assert "api_key" not in me.json()  # never returned again

        # ── Step 3: Create payment intent with idempotency key ─────────────
        idem_key = str(uuid4())
        create_resp = client.post(
            "/v1/payment-intents",
            json={"amount": 5000, "currency": "usd"},
            headers={**auth, "Idempotency-Key": idem_key},
        )
        assert create_resp.status_code == 201
        intent = create_resp.json()
        intent_id = intent["id"]
        assert intent["status"] == "CREATED"
        assert intent["amount"] == 5000

        # ── Step 4: Duplicate create returns same intent from cache ────────
        dup_create = client.post(
            "/v1/payment-intents",
            json={"amount": 5000, "currency": "usd"},
            headers={**auth, "Idempotency-Key": idem_key},
        )
        assert dup_create.json()["id"] == intent_id

        # ── Step 5: Confirm the payment (amount 5000 → last digit 0 → SUCCESS)
        confirm_idem = str(uuid4())
        confirm_resp = client.post(
            f"/v1/payment-intents/{intent_id}/confirm",
            headers={**auth, "Idempotency-Key": confirm_idem},
        )
        assert confirm_resp.status_code == 200
        confirmed = confirm_resp.json()
        assert confirmed["status"] == "SUCCEEDED"
        assert confirmed["failure_reason"] is None

        # ── Step 6: Ledger entries ─────────────────────────────────────────
        entries_resp = client.get("/v1/ledger/entries", headers=auth)
        assert entries_resp.status_code == 200
        entries = entries_resp.json()
        assert len(entries) == 2

        entry_types = {e["entry_type"] for e in entries}
        account_types = {e["account_type"] for e in entries}
        assert entry_types == {"DEBIT", "CREDIT"}
        assert account_types == {"CUSTOMER", "MERCHANT"}
        for e in entries:
            assert e["amount"] == 5000
            assert e["payment_intent_id"] == intent_id

        # ── Step 7: Merchant balance ───────────────────────────────────────
        balance_resp = client.get("/v1/ledger/balance", headers=auth)
        assert balance_resp.status_code == 200
        balance = balance_resp.json()
        assert balance["balance"] == 5000
        assert balance["total_received"] == 5000
        assert balance["currency"] == "usd"

        # ── Step 8: Global ledger invariant ───────────────────────────────
        with raw_conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    SUM(amount) FILTER (WHERE entry_type = 'DEBIT')  AS d,
                    SUM(amount) FILTER (WHERE entry_type = 'CREDIT') AS c
                FROM ledger_entries
                """
            )
            row = cur.fetchone()
        assert row["d"] == row["c"], "Global ledger invariant violated"

        # ── Step 9: Webhook outbox event ──────────────────────────────────
        with raw_conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM webhook_events WHERE payment_intent_id = %s",
                (intent_id,),
            )
            webhook_rows = cur.fetchall()

        assert len(webhook_rows) == 1
        event = webhook_rows[0]
        assert event["status"] == "PENDING"
        assert event["event_type"] == "payment_intent.succeeded"
        assert event["attempt_count"] == 0

        payload = event["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["payment_intent_id"] == intent_id
        assert payload["amount"] == 5000
        assert payload["status"] == "SUCCEEDED"

        # ── Step 10: HMAC signature verification ──────────────────────────
        from uuid import UUID
        payload_json = json.dumps(payload, sort_keys=True)
        from app.services.webhook_service import sign_payload
        expected_sig = sign_payload(UUID(merchant_id), payload_json)
        assert verify_signature(UUID(merchant_id), payload_json, expected_sig)

        # ── Step 11: Double confirm rejected ──────────────────────────────
        second_confirm = client.post(
            f"/v1/payment-intents/{intent_id}/confirm",
            headers=auth,
        )
        assert second_confirm.status_code == 409

        # ── Step 12: Cross-merchant isolation ─────────────────────────────
        other = client.post(
            "/v1/merchants",
            json={"name": "Other Corp", "email": "other@e2e.com"},
        ).json()
        other_auth = {"X-API-Key": other["api_key"]}

        assert client.get(f"/v1/payment-intents/{intent_id}", headers=other_auth).status_code == 404
        assert client.get("/v1/ledger/entries", headers=other_auth).json() == []
        assert client.get("/v1/ledger/balance", headers=other_auth).json()["balance"] == 0
