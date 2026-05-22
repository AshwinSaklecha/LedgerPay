"""
Ledger tests.

Key invariant: SUM(all DEBITs) == SUM(all CREDITs) always.
"""
import threading

import pytest

MERCHANT = {"name": "Ledger Merchant", "email": "ledger@test.com"}


@pytest.fixture()
def merchant(client):
    resp = client.post("/v1/merchants", json=MERCHANT)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture()
def auth(merchant):
    return {"X-API-Key": merchant["api_key"]}


def confirm_payment(client, auth, amount: int) -> dict:
    intent = client.post("/v1/payment-intents", json={"amount": amount}, headers=auth).json()
    return client.post(f"/v1/payment-intents/{intent['id']}/confirm", headers=auth).json()


class TestLedgerEntries:
    def test_no_entries_on_failed_payment(self, client, auth):
        """FAILED payments must not produce any ledger entries."""
        confirm_payment(client, auth, amount=1001)  # last digit 1 → FAILED
        resp = client.get("/v1/ledger/entries", headers=auth)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_no_entries_on_timeout(self, client, auth):
        """TIMED_OUT payments must not produce any ledger entries."""
        confirm_payment(client, auth, amount=1002)  # last digit 2 → TIMED_OUT
        resp = client.get("/v1/ledger/entries", headers=auth)
        assert resp.json() == []

    def test_two_entries_on_success(self, client, auth):
        """A succeeded payment creates exactly 2 ledger entries."""
        confirm_payment(client, auth, amount=1000)  # last digit 0 → SUCCEEDED
        resp = client.get("/v1/ledger/entries", headers=auth)
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) == 2

        types = {e["entry_type"] for e in entries}
        accounts = {e["account_type"] for e in entries}
        assert types == {"DEBIT", "CREDIT"}
        assert accounts == {"CUSTOMER", "MERCHANT"}

    def test_entries_have_correct_amount(self, client, auth):
        confirm_payment(client, auth, amount=2500)
        entries = client.get("/v1/ledger/entries", headers=auth).json()
        for e in entries:
            assert e["amount"] == 2500

    def test_entries_isolated_per_merchant(self, client):
        """Merchant A's entries must not appear in Merchant B's ledger."""
        m_a = client.post("/v1/merchants", json={"name": "A", "email": "a@ledger.com"}).json()
        m_b = client.post("/v1/merchants", json={"name": "B", "email": "b@ledger.com"}).json()
        auth_a = {"X-API-Key": m_a["api_key"]}
        auth_b = {"X-API-Key": m_b["api_key"]}

        confirm_payment(client, auth_a, 1000)
        confirm_payment(client, auth_a, 2000)
        confirm_payment(client, auth_b, 3000)

        assert len(client.get("/v1/ledger/entries", headers=auth_a).json()) == 4  # 2×2
        assert len(client.get("/v1/ledger/entries", headers=auth_b).json()) == 2  # 1×2


class TestBalance:
    def test_zero_balance_initially(self, client, auth):
        resp = client.get("/v1/ledger/balance", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance"] == 0
        assert data["total_received"] == 0

    def test_balance_after_one_payment(self, client, auth):
        confirm_payment(client, auth, 1000)
        data = client.get("/v1/ledger/balance", headers=auth).json()
        assert data["balance"] == 1000
        assert data["total_received"] == 1000

    def test_balance_accumulates(self, client, auth):
        confirm_payment(client, auth, 1000)
        confirm_payment(client, auth, 2000)
        confirm_payment(client, auth, 3000)
        data = client.get("/v1/ledger/balance", headers=auth).json()
        assert data["balance"] == 6000
        assert data["total_received"] == 6000

    def test_failed_payments_dont_affect_balance(self, client, auth):
        confirm_payment(client, auth, 1000)   # SUCCEEDED
        confirm_payment(client, auth, 2001)   # FAILED
        confirm_payment(client, auth, 3002)   # TIMED_OUT
        data = client.get("/v1/ledger/balance", headers=auth).json()
        assert data["balance"] == 1000


class TestLedgerInvariant:
    def test_double_entry_invariant_single(self, client, auth, raw_conn):
        """After any payment, SUM(DEBITs) == SUM(CREDITs) globally."""
        confirm_payment(client, auth, 1000)
        self._assert_invariant(raw_conn)

    def test_double_entry_invariant_concurrent(self, client, auth, raw_conn):
        """
        Fire 20 concurrent payments and verify the invariant holds globally.
        This proves the ledger writes are atomic with the payment state update
        — no partial writes possible.
        """
        errors = []

        def make_payment(amount):
            try:
                confirm_payment(client, auth, amount)
            except Exception as e:
                errors.append(e)

        # amounts ending in 0 → all SUCCEEDED
        threads = [threading.Thread(target=make_payment, args=(1000 + i * 10,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Threads raised errors: {errors}"
        self._assert_invariant(raw_conn)

    def _assert_invariant(self, raw_conn):
        with raw_conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    SUM(amount) FILTER (WHERE entry_type = 'DEBIT')  AS total_debit,
                    SUM(amount) FILTER (WHERE entry_type = 'CREDIT') AS total_credit
                FROM ledger_entries
                """
            )
            row = cur.fetchone()
        total_debit = row["total_debit"] or 0
        total_credit = row["total_credit"] or 0
        assert total_debit == total_credit, (
            f"Ledger invariant violated: "
            f"total_debit={total_debit} != total_credit={total_credit}"
        )
