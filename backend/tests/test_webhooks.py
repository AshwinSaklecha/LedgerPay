"""
Webhook tests.

Strategy:
  - Outbox insertion is tested at the API level (confirm payment, check DB row)
  - Delivery logic is tested by calling worker functions directly with a
    mocked requests.post — no real HTTP needed
  - HMAC signing is tested as a pure function
"""
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest

from app.services.webhook_service import sign_payload, verify_signature
from app.worker.webhook_worker import (
    _backoff_with_jitter,
    deliver_event,
    fetch_pending_events,
)

MERCHANT_WITH_WEBHOOK = {
    "name": "Webhook Merchant",
    "email": "webhook@test.com",
    "webhook_url": "https://merchant.example.com/hooks",
}
MERCHANT_NO_WEBHOOK = {
    "name": "No Webhook",
    "email": "noweb@test.com",
}


@pytest.fixture()
def merchant(client):
    return client.post("/v1/merchants", json=MERCHANT_WITH_WEBHOOK).json()


@pytest.fixture()
def auth(merchant):
    return {"X-API-Key": merchant["api_key"]}


@pytest.fixture()
def worker_conn():
    """A psycopg2 connection in autocommit=False mode for worker tests."""
    conn = psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()


class TestOutboxInsertion:
    def test_webhook_event_created_on_success(self, client, auth, raw_conn):
        """
        Confirming a succeeded payment must create a webhook_events row
        atomically in the same transaction.
        """
        intent = client.post("/v1/payment-intents", json={"amount": 1000}, headers=auth).json()
        client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)

        with raw_conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM webhook_events WHERE payment_intent_id = %s",
                (intent["id"],),
            )
            rows = cur.fetchall()

        assert len(rows) == 1
        event = rows[0]
        assert event["status"] == "PENDING"
        assert event["event_type"] == "payment_intent.succeeded"
        assert event["attempt_count"] == 0

    def test_no_webhook_event_on_failed_payment(self, client, auth, raw_conn):
        intent = client.post("/v1/payment-intents", json={"amount": 1001}, headers=auth).json()
        client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)

        with raw_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM webhook_events")
            assert cur.fetchone()["cnt"] == 0

    def test_no_webhook_event_on_timeout(self, client, auth, raw_conn):
        intent = client.post("/v1/payment-intents", json={"amount": 1002}, headers=auth).json()
        client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)

        with raw_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM webhook_events")
            assert cur.fetchone()["cnt"] == 0

    def test_merchant_without_webhook_url_still_gets_event(self, client, raw_conn):
        """The outbox event is always created — delivery is skipped by the worker."""
        m = client.post("/v1/merchants", json=MERCHANT_NO_WEBHOOK).json()
        auth = {"X-API-Key": m["api_key"]}
        intent = client.post("/v1/payment-intents", json={"amount": 2000}, headers=auth).json()
        client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)

        with raw_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM webhook_events")
            assert cur.fetchone()["cnt"] == 1


class TestHMACSigning:
    def test_sign_and_verify_roundtrip(self):
        merchant_id = uuid4()
        payload = json.dumps({"amount": 1000, "status": "SUCCEEDED"}, sort_keys=True)
        signature = sign_payload(merchant_id, payload)
        assert signature.startswith("sha256=")
        assert verify_signature(merchant_id, payload, signature)

    def test_wrong_merchant_fails_verification(self):
        merchant_id_a = uuid4()
        merchant_id_b = uuid4()
        payload = json.dumps({"amount": 1000}, sort_keys=True)
        signature = sign_payload(merchant_id_a, payload)
        assert not verify_signature(merchant_id_b, payload, signature)

    def test_tampered_payload_fails_verification(self):
        merchant_id = uuid4()
        payload = json.dumps({"amount": 1000}, sort_keys=True)
        signature = sign_payload(merchant_id, payload)
        tampered = json.dumps({"amount": 9999}, sort_keys=True)
        assert not verify_signature(merchant_id, tampered, signature)

    def test_different_payments_different_signatures(self):
        merchant_id = uuid4()
        p1 = json.dumps({"payment_id": "aaa"}, sort_keys=True)
        p2 = json.dumps({"payment_id": "bbb"}, sort_keys=True)
        assert sign_payload(merchant_id, p1) != sign_payload(merchant_id, p2)


class TestBackoff:
    def test_backoff_increases_with_attempts(self):
        delays = [_backoff_with_jitter(i) for i in range(4)]
        # Each delay should generally be larger than the previous
        # (with jitter it's not guaranteed, but the bases are 10/30/120/600)
        assert delays[3] > delays[0]

    def test_jitter_adds_randomness(self):
        delays = [_backoff_with_jitter(1) for _ in range(20)]
        assert len(set(delays)) > 1  # not all identical

    def test_minimum_delay_is_positive(self):
        for i in range(10):
            assert _backoff_with_jitter(i) >= 1.0


class TestWorkerDelivery:
    def _make_event(self, worker_conn, client, auth) -> dict:
        """Helper: create a succeeded payment and return its webhook event row."""
        intent = client.post("/v1/payment-intents", json={"amount": 1000}, headers=auth).json()
        client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)
        worker_conn.rollback()  # sync view
        events = fetch_pending_events(worker_conn)
        assert len(events) == 1
        return dict(events[0])

    def test_successful_delivery_marks_delivered(self, client, auth, worker_conn):
        event = self._make_event(worker_conn, client, auth)

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        with patch("app.worker.webhook_worker.requests.post", return_value=mock_resp) as mock_post:
            deliver_event(worker_conn, event)
            worker_conn.commit()

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        # Verify the signature header is present
        assert "X-LedgerPay-Signature" in call_kwargs.kwargs["headers"]
        sig = call_kwargs.kwargs["headers"]["X-LedgerPay-Signature"]
        assert sig.startswith("sha256=")

        # Check DB state
        with worker_conn.cursor() as cur:
            cur.execute("SELECT status, delivered_at FROM webhook_events WHERE id = %s", (str(event["id"]),))
            row = cur.fetchone()
        assert row["status"] == "DELIVERED"
        assert row["delivered_at"] is not None

    def test_failed_delivery_schedules_retry(self, client, auth, worker_conn):
        event = self._make_event(worker_conn, client, auth)

        with patch("app.worker.webhook_worker.requests.post", side_effect=Exception("connection refused")):
            deliver_event(worker_conn, event)
            worker_conn.commit()

        with worker_conn.cursor() as cur:
            cur.execute(
                "SELECT status, attempt_count, next_attempt_at FROM webhook_events WHERE id = %s",
                (str(event["id"]),),
            )
            row = cur.fetchone()

        assert row["status"] == "PENDING"
        assert row["attempt_count"] == 1
        assert row["next_attempt_at"] > datetime.now(tz=timezone.utc)

    def test_max_attempts_marks_failed(self, client, auth, worker_conn, raw_conn):
        event = self._make_event(worker_conn, client, auth)

        with patch("app.worker.webhook_worker.requests.post", side_effect=Exception("always fails")):
            for _ in range(5):
                with raw_conn.cursor() as cur:
                    cur.execute(
                        "UPDATE webhook_events SET next_attempt_at = NOW() WHERE id = %s",
                        (str(event["id"]),),
                    )
                events = fetch_pending_events(worker_conn)
                if not events:
                    break
                deliver_event(worker_conn, dict(events[0]))
                worker_conn.commit()

        with worker_conn.cursor() as cur:
            cur.execute("SELECT status, attempt_count FROM webhook_events WHERE id = %s", (str(event["id"]),))
            row = cur.fetchone()

        assert row["status"] == "FAILED"
        assert row["attempt_count"] == 5

    def test_worker_skips_merchant_without_webhook_url(self, client, worker_conn):
        m = client.post("/v1/merchants", json=MERCHANT_NO_WEBHOOK).json()
        auth = {"X-API-Key": m["api_key"]}
        intent = client.post("/v1/payment-intents", json={"amount": 2000}, headers=auth).json()
        client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)

        worker_conn.rollback()
        events = fetch_pending_events(worker_conn)
        # Worker query JOINs on webhook_url IS NOT NULL — event should not appear
        assert len(events) == 0
