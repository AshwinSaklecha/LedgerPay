"""
Payment intent tests.

Amount conventions (last digit controls mock bank outcome):
  xxxx0  →  SUCCEEDED
  xxxx1  →  FAILED
  xxxx2  →  TIMED_OUT
"""
import threading
import uuid

import pytest

MERCHANT = {"name": "Test Merchant", "email": "merchant@test.com"}


@pytest.fixture()
def merchant(client):
    resp = client.post("/v1/merchants", json=MERCHANT)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture()
def auth(merchant):
    return {"X-API-Key": merchant["api_key"]}


@pytest.fixture()
def intent(client, auth):
    resp = client.post("/v1/payment-intents", json={"amount": 1000}, headers=auth)
    assert resp.status_code == 201
    return resp.json()


class TestCreatePaymentIntent:
    def test_create_success(self, client, auth):
        resp = client.post("/v1/payment-intents", json={"amount": 1000}, headers=auth)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "CREATED"
        assert data["amount"] == 1000
        assert data["currency"] == "usd"

    def test_create_requires_auth(self, client):
        resp = client.post("/v1/payment-intents", json={"amount": 1000})
        assert resp.status_code == 401

    def test_create_invalid_amount(self, client, auth):
        resp = client.post("/v1/payment-intents", json={"amount": 0}, headers=auth)
        assert resp.status_code == 422

    def test_create_negative_amount(self, client, auth):
        resp = client.post("/v1/payment-intents", json={"amount": -500}, headers=auth)
        assert resp.status_code == 422

    def test_create_idempotency(self, client, auth):
        """Same Idempotency-Key returns the same intent, no duplicate created."""
        key = str(uuid.uuid4())
        headers = {**auth, "Idempotency-Key": key}

        resp1 = client.post("/v1/payment-intents", json={"amount": 1000}, headers=headers)
        resp2 = client.post("/v1/payment-intents", json={"amount": 1000}, headers=headers)

        assert resp1.status_code == 201
        assert resp2.status_code == 200 or resp2.status_code == 201  # cached hit
        assert resp1.json()["id"] == resp2.json()["id"]

        # Only one record in the DB
        list_resp = client.get("/v1/payment-intents", headers=auth)
        assert len(list_resp.json()) == 1


class TestConfirmPaymentIntent:
    def test_confirm_success(self, client, auth, intent):
        """amount=1000 → last digit 0 → SUCCEEDED"""
        resp = client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUCCEEDED"

    def test_confirm_decline(self, client, auth):
        """amount=1001 → last digit 1 → FAILED"""
        intent = client.post("/v1/payment-intents", json={"amount": 1001}, headers=auth).json()
        resp = client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "FAILED"
        assert data["failure_reason"] == "insufficient_funds"

    def test_confirm_timeout(self, client, auth):
        """amount=1002 → last digit 2 → TIMED_OUT"""
        intent = client.post("/v1/payment-intents", json={"amount": 1002}, headers=auth).json()
        resp = client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "TIMED_OUT"
        assert data["failure_reason"] == "bank_timeout"

    def test_confirm_nonexistent(self, client, auth):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/v1/payment-intents/{fake_id}/confirm", headers=auth)
        assert resp.status_code == 404

    def test_confirm_wrong_merchant(self, client):
        """Merchant A cannot confirm Merchant B's payment."""
        merchant_a = client.post("/v1/merchants", json={"name": "A", "email": "a@test.com"}).json()
        merchant_b = client.post("/v1/merchants", json={"name": "B", "email": "b@test.com"}).json()
        auth_a = {"X-API-Key": merchant_a["api_key"]}
        auth_b = {"X-API-Key": merchant_b["api_key"]}

        intent = client.post("/v1/payment-intents", json={"amount": 1000}, headers=auth_a).json()
        resp = client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth_b)
        assert resp.status_code == 404

    def test_double_confirm_rejected(self, client, auth, intent):
        """Second confirm on an already-confirmed intent returns 409."""
        client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)
        resp = client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)
        assert resp.status_code == 409

    def test_confirm_idempotency_key(self, client, auth, intent):
        """Same Idempotency-Key on confirm returns cached result."""
        key = str(uuid.uuid4())
        headers = {**auth, "Idempotency-Key": key}

        resp1 = client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=headers)
        resp2 = client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=headers)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["id"] == resp2.json()["id"]
        assert resp1.json()["status"] == resp2.json()["status"]


class TestGetAndListPaymentIntents:
    def test_get_by_id(self, client, auth, intent):
        resp = client.get(f"/v1/payment-intents/{intent['id']}", headers=auth)
        assert resp.status_code == 200
        assert resp.json()["id"] == intent["id"]

    def test_get_nonexistent(self, client, auth):
        resp = client.get(f"/v1/payment-intents/{uuid.uuid4()}", headers=auth)
        assert resp.status_code == 404

    def test_list_returns_merchant_intents_only(self, client):
        merchant_a = client.post("/v1/merchants", json={"name": "A", "email": "a2@test.com"}).json()
        merchant_b = client.post("/v1/merchants", json={"name": "B", "email": "b2@test.com"}).json()
        auth_a = {"X-API-Key": merchant_a["api_key"]}
        auth_b = {"X-API-Key": merchant_b["api_key"]}

        client.post("/v1/payment-intents", json={"amount": 1000}, headers=auth_a)
        client.post("/v1/payment-intents", json={"amount": 2000}, headers=auth_a)
        client.post("/v1/payment-intents", json={"amount": 3000}, headers=auth_b)

        resp_a = client.get("/v1/payment-intents", headers=auth_a)
        resp_b = client.get("/v1/payment-intents", headers=auth_b)

        assert len(resp_a.json()) == 2
        assert len(resp_b.json()) == 1


class TestRowLocking:
    def test_concurrent_confirms_only_one_succeeds(self, client, auth, intent):
        """
        Fire two concurrent confirm requests on the same intent.
        SELECT FOR UPDATE means one gets the lock and processes it;
        the other blocks, then sees status != CREATED and gets 409.
        """
        results = []

        def confirm():
            r = client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth)
            results.append(r.status_code)

        t1 = threading.Thread(target=confirm)
        t2 = threading.Thread(target=confirm)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one 200 and one 409
        assert sorted(results) == [200, 409]

        # Confirm the DB shows a single terminal state
        final = client.get(f"/v1/payment-intents/{intent['id']}", headers=auth).json()
        assert final["status"] in ("SUCCEEDED", "FAILED", "TIMED_OUT")
