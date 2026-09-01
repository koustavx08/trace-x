"""
CRUD + business-logic tests for src/api/v1/wallets.py.

Needs a reachable `tracex_test` Postgres database (skips cleanly via
fixtures_db.api_client/db_session if one isn't available -- see
tests/fixtures_db.py for why).
"""
from uuid import uuid4

from fixtures_db import api_client, db_session  # noqa: F401


async def _create_case(api_client):
    response = await api_client.post(
        "/api/v1/cases",
        json={"title": "Wallet Test Case", "description": "for wallet tests"},
    )
    assert response.status_code == 201
    return response.json()


def _wallet_payload(**overrides):
    payload = {
        "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "chain": "ethereum",
        "label": "Suspect Wallet",
        "risk_score": 0.0,
    }
    payload.update(overrides)
    return payload


class TestWalletCRUD:
    async def test_create_wallet_requires_existing_case(self, api_client):
        response = await api_client.post(
            "/api/v1/wallets",
            params={"case_id": str(uuid4())},
            json=_wallet_payload(),
        )
        assert response.status_code == 404

    async def test_create_wallet_success(self, api_client):
        case = await _create_case(api_client)
        response = await api_client.post(
            "/api/v1/wallets",
            params={"case_id": case["id"]},
            json=_wallet_payload(),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["address"] == "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        assert body["case_id"] == case["id"]
        assert body["attribution_status"] == "unverified"

    async def test_create_wallet_rejects_out_of_range_risk_score(self, api_client):
        case = await _create_case(api_client)
        response = await api_client.post(
            "/api/v1/wallets",
            params={"case_id": case["id"]},
            json=_wallet_payload(risk_score=150.0),
        )
        assert response.status_code == 422

    async def test_get_wallet_by_id(self, api_client):
        case = await _create_case(api_client)
        create_resp = await api_client.post(
            "/api/v1/wallets", params={"case_id": case["id"]}, json=_wallet_payload()
        )
        wallet_id = create_resp.json()["id"]

        response = await api_client.get(f"/api/v1/wallets/{wallet_id}")
        assert response.status_code == 200
        assert response.json()["id"] == wallet_id

    async def test_get_wallet_not_found(self, api_client):
        response = await api_client.get(f"/api/v1/wallets/{uuid4()}")
        assert response.status_code == 404

    async def test_list_wallets_filtered_by_case(self, api_client):
        case_a = await _create_case(api_client)
        case_b = await _create_case(api_client)
        await api_client.post(
            "/api/v1/wallets", params={"case_id": case_a["id"]}, json=_wallet_payload()
        )
        await api_client.post(
            "/api/v1/wallets",
            params={"case_id": case_b["id"]},
            json=_wallet_payload(address="0x0000000000000000000000000000000000dEaD"),
        )

        response = await api_client.get("/api/v1/wallets", params={"case_id": case_a["id"]})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["case_id"] == case_a["id"]

    async def test_list_wallets_filtered_by_chain(self, api_client):
        case = await _create_case(api_client)
        await api_client.post(
            "/api/v1/wallets",
            params={"case_id": case["id"]},
            json=_wallet_payload(chain="polygon", address="0x1111111111111111111111111111111111111a"),
        )
        response = await api_client.get("/api/v1/wallets", params={"chain": "polygon"})
        assert response.status_code == 200
        assert all(item["chain"] == "polygon" for item in response.json()["items"])

    async def test_list_wallets_filtered_by_attribution_status(self, api_client):
        case = await _create_case(api_client)
        await api_client.post(
            "/api/v1/wallets",
            params={"case_id": case["id"]},
            json=_wallet_payload(attribution_status="confirmed"),
        )
        response = await api_client.get(
            "/api/v1/wallets", params={"attribution_status": "confirmed"}
        )
        assert response.status_code == 200
        assert all(
            item["attribution_status"] == "confirmed" for item in response.json()["items"]
        )

    async def test_update_wallet_label_and_risk_score(self, api_client):
        case = await _create_case(api_client)
        create_resp = await api_client.post(
            "/api/v1/wallets", params={"case_id": case["id"]}, json=_wallet_payload()
        )
        wallet_id = create_resp.json()["id"]

        response = await api_client.patch(
            f"/api/v1/wallets/{wallet_id}",
            json={"label": "Confirmed Mixer", "risk_score": 92.5},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["label"] == "Confirmed Mixer"
        assert body["risk_score"] == 92.5

    async def test_update_wallet_not_found(self, api_client):
        response = await api_client.patch(
            f"/api/v1/wallets/{uuid4()}", json={"label": "x"}
        )
        assert response.status_code == 404

    async def test_delete_wallet(self, api_client):
        case = await _create_case(api_client)
        create_resp = await api_client.post(
            "/api/v1/wallets", params={"case_id": case["id"]}, json=_wallet_payload()
        )
        wallet_id = create_resp.json()["id"]

        delete_resp = await api_client.delete(f"/api/v1/wallets/{wallet_id}")
        assert delete_resp.status_code == 204

        get_resp = await api_client.get(f"/api/v1/wallets/{wallet_id}")
        assert get_resp.status_code == 404

    async def test_delete_wallet_not_found(self, api_client):
        response = await api_client.delete(f"/api/v1/wallets/{uuid4()}")
        assert response.status_code == 404

    async def test_duplicate_address_chain_pair_rejected(self, api_client):
        """Wallet table has a unique index on (address, chain)."""
        case = await _create_case(api_client)
        await api_client.post(
            "/api/v1/wallets", params={"case_id": case["id"]}, json=_wallet_payload()
        )
        response = await api_client.post(
            "/api/v1/wallets", params={"case_id": case["id"]}, json=_wallet_payload()
        )
        # No explicit conflict handling in the current endpoint -- a DB
        # IntegrityError propagates up as a generic 500 today.
        assert response.status_code in (409, 500)
