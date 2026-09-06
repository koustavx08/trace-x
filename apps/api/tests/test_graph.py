"""
Tests for src/api/v1/graph.py.

The graph endpoints delegate to `graph_repository`/`graph_queries`
(src/graph/repository.py, src/graph/queries.py), which run raw Cypher
against Neo4j, and to `entity_intelligence`. Rather than requiring a real
Neo4j instance (not available in every dev/CI environment), these tests
monkeypatch those singletons' methods with canned async responses, so the
FastAPI routing/validation/wallet-lookup logic in graph.py is exercised
directly and deterministically. Endpoints that also look up a `Wallet` row
first still need a reachable `tracex_test` Postgres database and skip
cleanly if one isn't available (see tests/fixtures_db.py).
"""

from unittest.mock import AsyncMock
from uuid import uuid4

from fixtures_db import api_client, db_session  # noqa: F401

import src.api.v1.graph as graph_module


async def _create_case_and_wallet(api_client):
    case_resp = await api_client.post(
        "/api/v1/cases",
        json={"title": "Graph Test Case", "description": "for graph tests"},
    )
    case = case_resp.json()
    wallet_resp = await api_client.post(
        "/api/v1/wallets",
        params={"case_id": case["id"]},
        json={
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "chain": "ethereum",
        },
    )
    return case, wallet_resp.json()


# ---------------------------------------------------------------------------
# Endpoints that don't need a Postgres-backed Wallet lookup
# ---------------------------------------------------------------------------


class TestGraphEndpointsNoWalletLookup:
    async def test_get_subgraph(self, monkeypatch, api_client):
        monkeypatch.setattr(
            graph_module.graph_repository,
            "get_subgraph",
            AsyncMock(return_value={"nodes": [{"id": "Wallet:ethereum:0xabc"}], "edges": []}),
        )
        response = await api_client.post(
            "/api/v1/graph/subgraph",
            json={"addresses": ["0xabc"], "chain": "ethereum", "depth": 2},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["nodes"][0]["id"] == "Wallet:ethereum:0xabc"

    async def test_detect_patterns_peel_chain(self, monkeypatch, api_client):
        monkeypatch.setattr(
            graph_module.graph_queries,
            "detect_peel_chains",
            AsyncMock(return_value=[{"total_value": 5.0}]),
        )
        response = await api_client.post(
            "/api/v1/graph/patterns/detect",
            json={"chain": "ethereum", "pattern_type": "peel_chain"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["pattern_type"] == "peel_chain"
        assert body["count"] == 1

    async def test_detect_patterns_invalid_type_rejected(self, api_client):
        response = await api_client.post(
            "/api/v1/graph/patterns/detect",
            json={"chain": "ethereum", "pattern_type": "not_a_real_pattern"},
        )
        assert response.status_code == 422

    async def test_detect_clusters(self, monkeypatch, api_client):
        monkeypatch.setattr(
            graph_module.graph_repository,
            "detect_clusters",
            AsyncMock(return_value=[{"community": 1, "avg_risk": 80.0}]),
        )
        response = await api_client.post(
            "/api/v1/graph/clusters/detect",
            json={"chain": "ethereum", "min_cluster_size": 3},
        )
        assert response.status_code == 200
        assert response.json()["count"] == 1

    async def test_lookup_entity_found(self, monkeypatch, api_client):
        from src.graph.models import ConfidenceLevel, EntityType, GraphEntity

        entity = GraphEntity(
            name="Binance",
            entity_type=EntityType.EXCHANGE,
            address="0xabc",
            chain="ethereum",
            confidence=ConfidenceLevel.CONFIRMED,
        )
        monkeypatch.setattr(
            graph_module.entity_intelligence, "lookup_entity", AsyncMock(return_value=entity)
        )
        response = await api_client.post(
            "/api/v1/graph/entities/lookup", json={"address": "0xabc", "chain": "ethereum"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["found"] is True
        assert body["entity"]["name"] == "Binance"

    async def test_lookup_entity_not_found(self, monkeypatch, api_client):
        monkeypatch.setattr(
            graph_module.entity_intelligence, "lookup_entity", AsyncMock(return_value=None)
        )
        response = await api_client.post(
            "/api/v1/graph/entities/lookup", json={"address": "0xdead", "chain": "ethereum"}
        )
        assert response.status_code == 200
        assert response.json()["found"] is False

    async def test_sync_entities(self, monkeypatch, api_client):
        monkeypatch.setattr(
            graph_module.entity_intelligence,
            "sync_to_graph",
            AsyncMock(return_value={"exchanges": 10, "mixers": 3}),
        )
        response = await api_client.post("/api/v1/graph/entities/sync")
        assert response.status_code == 200
        assert response.json()["exchanges"] == 10

    async def test_graph_health_reports_unhealthy_without_neo4j(self, api_client):
        # No mocking here on purpose -- this documents real behavior: when
        # Neo4j isn't reachable, the endpoint should degrade gracefully
        # (200 with an "unhealthy" body), never raise.
        response = await api_client.get("/api/v1/graph/health")
        assert response.status_code == 200
        assert response.json()["status"] in ("healthy", "unhealthy")


# ---------------------------------------------------------------------------
# Endpoints that look up a Wallet row (need Postgres) + mocked graph calls
# ---------------------------------------------------------------------------


class TestGraphEndpointsWithWalletLookup:
    async def test_sync_wallet_to_graph_unknown_wallet_404(self, api_client):
        response = await api_client.post(
            "/api/v1/graph/wallets/sync", params={"wallet_id": str(uuid4())}
        )
        assert response.status_code == 404

    async def test_sync_wallet_to_graph_success(self, api_client):
        """The endpoint dispatches to Celery and answers 202 immediately.

        It no longer syncs inline (it returns "queued" plus the task id, not
        "synced"), so there is nothing on graph_repository to stub here -- the
        work happens in the worker.
        """
        _, wallet = await _create_case_and_wallet(api_client)
        response = await api_client.post(
            "/api/v1/graph/wallets/sync", params={"wallet_id": wallet["id"]}
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert body["wallet_id"] == wallet["id"]
        assert body["task_id"]

    async def test_paths_to_vasp_unknown_wallet_404(self, api_client):
        response = await api_client.post(
            f"/api/v1/graph/wallets/{uuid4()}/paths-to-vasp",
            json={"wallet_id": str(uuid4()), "max_hops": 6},
        )
        assert response.status_code == 404

    async def test_paths_to_vasp_success(self, monkeypatch, api_client):
        _, wallet = await _create_case_and_wallet(api_client)
        monkeypatch.setattr(
            graph_module.graph_repository, "find_paths_to_entities", AsyncMock(return_value=[])
        )
        response = await api_client.post(
            f"/api/v1/graph/wallets/{wallet['id']}/paths-to-vasp",
            json={"wallet_id": wallet["id"], "max_hops": 6},
        )
        assert response.status_code == 200
        assert response.json()["paths"] == []

    async def test_mixer_check_success(self, monkeypatch, api_client):
        _, wallet = await _create_case_and_wallet(api_client)
        monkeypatch.setattr(
            graph_module.graph_queries,
            "find_mixer_interactions",
            AsyncMock(return_value=[{"mixer": "tornado_cash"}]),
        )
        response = await api_client.post(f"/api/v1/graph/wallets/{wallet['id']}/mixer-check")
        assert response.status_code == 200
        assert response.json()["mixer_interactions"] == [{"mixer": "tornado_cash"}]

    async def test_wallet_stats_success(self, monkeypatch, api_client):
        _, wallet = await _create_case_and_wallet(api_client)
        monkeypatch.setattr(
            graph_module.graph_repository,
            "get_wallet_stats",
            AsyncMock(return_value={"tx_count": 42}),
        )
        response = await api_client.get(f"/api/v1/graph/wallets/{wallet['id']}/stats")
        assert response.status_code == 200
        assert response.json()["tx_count"] == 42

    async def test_wallet_stats_unknown_wallet_404(self, api_client):
        response = await api_client.get(f"/api/v1/graph/wallets/{uuid4()}/stats")
        assert response.status_code == 404

    async def test_wallet_centrality_success(self, monkeypatch, api_client):
        _, wallet = await _create_case_and_wallet(api_client)
        monkeypatch.setattr(
            graph_module.graph_queries,
            "get_wallet_centrality",
            AsyncMock(return_value=[{"address": "0xabc", "score": 0.9}]),
        )
        response = await api_client.get(
            f"/api/v1/graph/wallets/{wallet['id']}/centrality",
            params={"algorithm": "pagerank"},
        )
        assert response.status_code == 200
        assert response.json()["algorithm"] == "pagerank"

    async def test_wallet_centrality_invalid_algorithm_rejected(self, api_client):
        _, wallet = await _create_case_and_wallet(api_client)
        response = await api_client.get(
            f"/api/v1/graph/wallets/{wallet['id']}/centrality",
            params={"algorithm": "not_a_real_algorithm"},
        )
        assert response.status_code == 422

    async def test_temporal_flow_success(self, monkeypatch, api_client):
        _, wallet = await _create_case_and_wallet(api_client)
        monkeypatch.setattr(
            graph_module.graph_queries,
            "get_temporal_flow",
            AsyncMock(return_value=[{"bucket": "2024-01-01", "tx_count": 3}]),
        )
        response = await api_client.get(
            f"/api/v1/graph/wallets/{wallet['id']}/temporal-flow",
            params={"start_date": "2024-01-01", "end_date": "2024-02-01", "bucket": "day"},
        )
        assert response.status_code == 200
        assert len(response.json()["temporal_flow"]) == 1

    async def test_enrich_wallet_success(self, api_client):
        """Enrichment is queued to Celery too -- 202 "queued", not an inline 200."""
        _, wallet = await _create_case_and_wallet(api_client)
        response = await api_client.post(
            "/api/v1/graph/entities/enrich", params={"wallet_id": wallet["id"]}
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert body["wallet_id"] == wallet["id"]
        assert body["task_id"]

    async def test_enrich_wallet_unknown_wallet_404(self, api_client):
        response = await api_client.post(
            "/api/v1/graph/entities/enrich", params={"wallet_id": str(uuid4())}
        )
        assert response.status_code == 404
