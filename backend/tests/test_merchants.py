import pytest


REGISTER_PAYLOAD = {
    "name": "Acme Corp",
    "email": "acme@example.com",
    "webhook_url": "https://acme.example.com/webhooks",
}


class TestMerchantRegistration:
    def test_register_success(self, client):
        resp = client.post("/v1/merchants", json=REGISTER_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == REGISTER_PAYLOAD["email"]
        assert data["name"] == REGISTER_PAYLOAD["name"]
        assert data["api_key"].startswith("lp_")
        assert len(data["api_key"]) == 67  # "lp_" + 64 hex chars
        assert "id" in data
        assert "created_at" in data

    def test_register_returns_api_key_once(self, client):
        resp = client.post("/v1/merchants", json=REGISTER_PAYLOAD)
        assert resp.status_code == 201
        # The key must be in the response body
        assert "api_key" in resp.json()

    def test_register_duplicate_email(self, client):
        client.post("/v1/merchants", json=REGISTER_PAYLOAD)
        resp = client.post("/v1/merchants", json=REGISTER_PAYLOAD)
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    def test_register_without_webhook_url(self, client):
        payload = {"name": "No Webhook Co", "email": "noweb@example.com"}
        resp = client.post("/v1/merchants", json=payload)
        assert resp.status_code == 201
        assert resp.json()["webhook_url"] is None

    def test_register_invalid_email(self, client):
        payload = {**REGISTER_PAYLOAD, "email": "not-an-email"}
        resp = client.post("/v1/merchants", json=payload)
        assert resp.status_code == 422


class TestMerchantAuth:
    def test_get_me_success(self, client):
        reg = client.post("/v1/merchants", json=REGISTER_PAYLOAD).json()
        api_key = reg["api_key"]

        resp = client.get("/v1/merchants/me", headers={"X-API-Key": api_key})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == REGISTER_PAYLOAD["email"]
        assert "api_key" not in data  # key is never returned again

    def test_get_me_no_key(self, client):
        resp = client.get("/v1/merchants/me")
        assert resp.status_code == 401

    def test_get_me_wrong_key(self, client):
        client.post("/v1/merchants", json=REGISTER_PAYLOAD)
        resp = client.get("/v1/merchants/me", headers={"X-API-Key": "lp_wrongkey"})
        assert resp.status_code == 401

    def test_get_me_tampered_key(self, client):
        reg = client.post("/v1/merchants", json=REGISTER_PAYLOAD).json()
        tampered = reg["api_key"][:-4] + "aaaa"
        resp = client.get("/v1/merchants/me", headers={"X-API-Key": tampered})
        assert resp.status_code == 401
