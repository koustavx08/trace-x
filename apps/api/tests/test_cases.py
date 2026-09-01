"""
CRUD + business-logic tests for src/api/v1/cases.py.

Needs a reachable `tracex_test` Postgres database (skips cleanly via
fixtures_db.api_client/db_session if one isn't available -- see
tests/fixtures_db.py for why).
"""
from uuid import uuid4

from fixtures_db import api_client, db_session  # noqa: F401


def _case_payload(**overrides):
    payload = {
        "title": "Test Fraud Case",
        "crime_type": "fraud",
        "description": "A test case created by the automated test suite.",
        "status": "open",
    }
    payload.update(overrides)
    return payload


class TestCaseCRUD:
    async def test_create_case_generates_case_number(self, api_client):
        response = await api_client.post("/api/v1/cases", json=_case_payload())
        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Test Fraud Case"
        assert body["case_number"].startswith("TRX-")
        assert body["status"] == "open"

    async def test_create_case_defaults_crime_type_and_status(self, api_client):
        response = await api_client.post(
            "/api/v1/cases",
            json={"title": "Minimal Case", "description": "minimal"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["crime_type"] == "fraud"
        assert body["status"] == "open"

    async def test_create_case_requires_title(self, api_client):
        response = await api_client.post(
            "/api/v1/cases", json={"description": "missing title"}
        )
        assert response.status_code == 422

    async def test_create_case_rejects_invalid_crime_type(self, api_client):
        response = await api_client.post(
            "/api/v1/cases",
            json=_case_payload(crime_type="not_a_real_crime_type"),
        )
        assert response.status_code == 422

    async def test_get_case_by_id(self, api_client):
        create_resp = await api_client.post("/api/v1/cases", json=_case_payload())
        case_id = create_resp.json()["id"]

        response = await api_client.get(f"/api/v1/cases/{case_id}")
        assert response.status_code == 200
        assert response.json()["id"] == case_id

    async def test_get_case_not_found(self, api_client):
        response = await api_client.get(f"/api/v1/cases/{uuid4()}")
        assert response.status_code == 404

    async def test_list_cases_pagination(self, api_client):
        for i in range(5):
            await api_client.post(
                "/api/v1/cases", json=_case_payload(title=f"Pagination Case {i}")
            )

        response = await api_client.get(
            "/api/v1/cases", params={"page": 1, "page_size": 2}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["page"] == 1
        assert body["page_size"] == 2
        assert len(body["items"]) == 2
        assert body["total"] >= 5

    async def test_list_cases_filtered_by_status(self, api_client):
        await api_client.post("/api/v1/cases", json=_case_payload(status="open"))
        create_resp = await api_client.post(
            "/api/v1/cases", json=_case_payload(status="closed", title="Closed Case")
        )
        assert create_resp.status_code == 201

        response = await api_client.get("/api/v1/cases", params={"status": "closed"})
        assert response.status_code == 200
        assert all(item["status"] == "closed" for item in response.json()["items"])

    async def test_list_cases_filtered_by_crime_type(self, api_client):
        await api_client.post(
            "/api/v1/cases", json=_case_payload(crime_type="ransomware", title="Ransomware Case")
        )
        response = await api_client.get(
            "/api/v1/cases", params={"crime_type": "ransomware"}
        )
        assert response.status_code == 200
        assert all(item["crime_type"] == "ransomware" for item in response.json()["items"])

    async def test_update_case_status(self, api_client):
        create_resp = await api_client.post("/api/v1/cases", json=_case_payload())
        case_id = create_resp.json()["id"]

        response = await api_client.patch(
            f"/api/v1/cases/{case_id}", json={"status": "in_progress"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"

    async def test_update_case_partial_update_preserves_other_fields(self, api_client):
        create_resp = await api_client.post("/api/v1/cases", json=_case_payload())
        case_id = create_resp.json()["id"]
        original_title = create_resp.json()["title"]

        response = await api_client.patch(
            f"/api/v1/cases/{case_id}", json={"status": "closed"}
        )
        assert response.json()["title"] == original_title

    async def test_update_case_not_found(self, api_client):
        response = await api_client.patch(
            f"/api/v1/cases/{uuid4()}", json={"status": "closed"}
        )
        assert response.status_code == 404

    async def test_delete_case(self, api_client):
        create_resp = await api_client.post("/api/v1/cases", json=_case_payload())
        case_id = create_resp.json()["id"]

        delete_resp = await api_client.delete(f"/api/v1/cases/{case_id}")
        assert delete_resp.status_code == 204

        get_resp = await api_client.get(f"/api/v1/cases/{case_id}")
        assert get_resp.status_code == 404

    async def test_delete_case_not_found(self, api_client):
        response = await api_client.delete(f"/api/v1/cases/{uuid4()}")
        assert response.status_code == 404

    async def test_case_number_uniqueness_across_multiple_creates(self, api_client):
        ids = set()
        for _ in range(5):
            resp = await api_client.post("/api/v1/cases", json=_case_payload())
            ids.add(resp.json()["case_number"])
        assert len(ids) == 5
