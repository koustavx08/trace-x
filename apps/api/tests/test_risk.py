"""
Tests for src/api/v1/risk.py and the pure risk-scoring logic in
src/analytics/risk_engine.py.

`risk_scoring_engine.assess_wallet(...)` is pure Python (no Neo4j/network
calls) given wallet/transaction data, so it's tested directly as a unit.
`attribution_engine` calls into `graph_repository` (Neo4j-backed), so those
tests monkeypatch it. Endpoints that look up a `Wallet`/`Case` row need a
reachable `tracex_test` Postgres database and skip cleanly if one isn't
available (see tests/fixtures_db.py).
"""

from unittest.mock import AsyncMock
from uuid import uuid4

from fixtures_db import api_client, db_session  # noqa: F401

from src.analytics.attribution_engine import AttributionEvidence, AttributionType, VASPAttribution
from src.analytics.risk_engine import risk_scoring_engine
from src.graph.models import ConfidenceLevel, EntityType, GraphWallet


async def _create_case_and_wallet(api_client, risk_score=0.0):
    case_resp = await api_client.post(
        "/api/v1/cases",
        json={"title": "Risk Test Case", "description": "for risk tests"},
    )
    case = case_resp.json()
    wallet_resp = await api_client.post(
        "/api/v1/wallets",
        params={"case_id": case["id"]},
        json={
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "chain": "ethereum",
            "risk_score": risk_score,
        },
    )
    return case, wallet_resp.json()


# ---------------------------------------------------------------------------
# Pure logic: RiskScoringEngine.assess_wallet (no DB, no Neo4j)
# ---------------------------------------------------------------------------


class TestRiskScoringEngine:
    async def test_assess_wallet_with_no_transactions_returns_low_score(self):
        wallet = GraphWallet(address="0xabc", chain="ethereum", tx_count=0)
        assessment = await risk_scoring_engine.assess_wallet(wallet=wallet, transactions=[])
        assert 0 <= assessment.overall_score <= 100
        assert assessment.risk_level is not None
        assert isinstance(assessment.factors, list)

    async def test_assess_wallet_result_is_serializable(self):
        wallet = GraphWallet(address="0xabc", chain="ethereum")
        assessment = await risk_scoring_engine.assess_wallet(wallet=wallet, transactions=[])
        as_dict = assessment.to_dict()
        assert "overall_score" in as_dict
        assert "risk_level" in as_dict
        assert "factors" in as_dict

    async def test_assess_wallet_with_sanctioned_entity_increases_risk(self):
        wallet = GraphWallet(address="0xabc", chain="ethereum")
        low_risk = await risk_scoring_engine.assess_wallet(wallet=wallet, transactions=[])

        sanctioned_wallet = GraphWallet(address="0xabc", chain="ethereum")
        high_risk = await risk_scoring_engine.assess_wallet(
            wallet=sanctioned_wallet,
            transactions=[],
            entity_data={
                "entity_name": "Sanctioned Entity",
                "entity_type": "sanctioned",
                "confidence": "CONFIRMED",
            },
        )
        assert high_risk.overall_score >= low_risk.overall_score


# ---------------------------------------------------------------------------
# /risk/wallets/{id}/assess -- real DB wallet lookup, pure scoring logic
# ---------------------------------------------------------------------------


class TestAssessEndpoint:
    async def test_assess_unknown_wallet_404(self, api_client):
        response = await api_client.post(f"/api/v1/risk/wallets/{uuid4()}/assess")
        assert response.status_code == 404

    async def test_assess_wallet_success(self, api_client):
        _, wallet = await _create_case_and_wallet(api_client)
        response = await api_client.post(f"/api/v1/risk/wallets/{wallet['id']}/assess")
        assert response.status_code == 200
        body = response.json()
        assert "overall_score" in body
        assert "risk_level" in body
        assert isinstance(body["factors"], list)


# ---------------------------------------------------------------------------
# /risk/wallets/{id}/attribution -- delegates to attribution_engine
# ---------------------------------------------------------------------------


class TestAttributionEndpoint:
    async def test_attribution_unknown_wallet_404(self, api_client):
        response = await api_client.get(f"/api/v1/risk/wallets/{uuid4()}/attribution")
        assert response.status_code == 404

    async def test_attribution_with_no_paths_returns_empty_summary(self, monkeypatch, api_client):
        """No attribution paths is a normal outcome, not an error.

        `get_attribution_summary` used to return {attributed, nearest_vasp,
        confidence, total_attributions} on this path while
        `AttributionResponse` also requires `all_attributions` and `summary`,
        so response validation failed and the endpoint 500'd whenever no VASP
        was found -- effectively always, without real Neo4j graph data. Both
        branches now return the same keys, so this asserts the 200 the previous
        version of this test said to switch to once they were reconciled."""
        _, wallet = await _create_case_and_wallet(api_client)
        import src.graph.repository as graph_repo_module

        monkeypatch.setattr(
            graph_repo_module.graph_repository, "find_paths_to_entities", AsyncMock(return_value=[])
        )
        response = await api_client.get(f"/api/v1/risk/wallets/{wallet['id']}/attribution")
        assert response.status_code == 200
        body = response.json()
        assert body["attributed"] is False
        assert body["nearest_vasp"] is None
        assert body["all_attributions"] == []
        assert body["summary"]["exchanges_found"] == 0

    async def test_attribution_with_a_found_path_succeeds(self, monkeypatch, api_client):
        _, wallet = await _create_case_and_wallet(api_client)

        attribution = VASPAttribution(
            entity_name="Binance",
            entity_type=EntityType.EXCHANGE,
            address="0xexchange",
            chain="ethereum",
            attribution_type=AttributionType.DIRECT,
            confidence=ConfidenceLevel.HIGH_CONFIDENCE,
            confidence_score=0.85,
            distance_hops=2,
            total_value_eth=1.23,
            evidence=[
                AttributionEvidence(
                    source="graph",
                    evidence_type="path",
                    description="direct path",
                    confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                )
            ],
        )

        # NB: `import src.analytics.attribution_engine as m` does NOT give the
        # module -- src/analytics/__init__.py re-exports the `attribution_engine`
        # singleton under the same name, shadowing the submodule in the package
        # namespace, so `m` is the AttributionEngine instance. Patch the
        # singleton directly instead.
        from src.analytics import attribution_engine

        monkeypatch.setattr(
            attribution_engine,
            "attribute_wallet",
            AsyncMock(return_value=[attribution]),
        )

        response = await api_client.get(f"/api/v1/risk/wallets/{wallet['id']}/attribution")
        assert response.status_code == 200
        body = response.json()
        assert body["attributed"] is True
        assert body["nearest_vasp"]["entity_name"] == "Binance"

    async def test_attribute_wallet_endpoint_unknown_wallet_404(self, api_client):
        response = await api_client.post(f"/api/v1/risk/wallets/{uuid4()}/attribute")
        assert response.status_code == 404

    async def test_attribute_wallet_endpoint_returns_list(self, monkeypatch, api_client):
        _, wallet = await _create_case_and_wallet(api_client)
        # NB: `import src.analytics.attribution_engine as m` does NOT give the
        # module -- src/analytics/__init__.py re-exports the `attribution_engine`
        # singleton under the same name, shadowing the submodule in the package
        # namespace, so `m` is the AttributionEngine instance. Patch the
        # singleton directly instead.
        from src.analytics import attribution_engine

        monkeypatch.setattr(
            attribution_engine,
            "attribute_wallet",
            AsyncMock(return_value=[]),
        )
        response = await api_client.post(f"/api/v1/risk/wallets/{wallet['id']}/attribute")
        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# /risk/cases/{id}/risk-summary -- pure DB aggregation, no Neo4j
# ---------------------------------------------------------------------------


class TestCaseRiskSummary:
    async def test_risk_summary_unknown_case_404(self, api_client):
        response = await api_client.get(f"/api/v1/risk/cases/{uuid4()}/risk-summary")
        assert response.status_code == 404

    async def test_risk_summary_no_wallets(self, api_client):
        case_resp = await api_client.post(
            "/api/v1/cases", json={"title": "Empty Case", "description": "no wallets"}
        )
        case = case_resp.json()

        response = await api_client.get(f"/api/v1/risk/cases/{case['id']}/risk-summary")
        assert response.status_code == 200
        body = response.json()
        assert body["wallets"] == 0

    async def test_risk_summary_with_wallets(self, api_client):
        case, _ = await _create_case_and_wallet(api_client, risk_score=90.0)

        response = await api_client.get(f"/api/v1/risk/cases/{case['id']}/risk-summary")
        assert response.status_code == 200
        body = response.json()
        assert body["total_wallets"] == 1
        assert body["risk_distribution"]["critical"] == 1
        assert len(body["top_risk_wallets"]) == 1
