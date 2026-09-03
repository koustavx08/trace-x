"""
Tests for src/ai/service.py (InvestigationAssistant, template-based today)
and src/ai/api.py (/ai/* endpoints).

WS2 ("Backend AI - Claude Integration") will replace the regex-based
`classify_query`/`_handle_*` dispatch with real Claude calls, falling back
to the current template logic only when `ANTHROPIC_API_KEY` is unset. This
worktree has no `anthropic` dependency and no Claude wiring at all yet, so
these tests exercise the current template/regex behavior directly. They
are written so the endpoint-level assertions (status codes, response
shape) should keep holding once WS2 lands and the assistant starts
returning Claude-backed prose instead of templated strings; the
`test_capabilities_reports_template_mode_honestly` test documents the one
place ("live-vs-template mode") that is expected to need a fixup once
`ANTHROPIC_API_KEY` support exists.
"""

from uuid import uuid4

import pytest
from fixtures_db import api_client, db_session  # noqa: F401
from httpx import ASGITransport, AsyncClient

from src.ai.service import InvestigationAssistant, QueryType, investigation_assistant
from src.graph.models import ConfidenceLevel
from src.main import app

# ---------------------------------------------------------------------------
# Pure logic: query classification / entity extraction (no DB, no network)
# ---------------------------------------------------------------------------


class TestClassifyQuery:
    @pytest.mark.parametrize(
        "query,expected_type",
        [
            ("What's the risk score for wallet 0x123?", QueryType.RISK_SUMMARY),
            ("How risky is this address?", QueryType.RISK_SUMMARY),
            ("Where did the funds from 0x... go?", QueryType.ATTRIBUTION),
            ("Which exchange did the money end up at?", QueryType.ATTRIBUTION),
            ("Any suspicious patterns on Ethereum?", QueryType.PATTERN_DETECTION),
            ("Detect peel chains in case TRX-1", QueryType.PATTERN_DETECTION),
            ("Trace the money from wallet 0x...", QueryType.FUND_FLOW),
            ("Follow the money from this wallet", QueryType.FUND_FLOW),
            ("Who owns address 0xabc?", QueryType.ENTITY_LOOKUP),
            ("Tell me about case TRX-20240115-0042", QueryType.CASE_OVERVIEW),
            ("Show me transaction timeline for wallet 0x...", QueryType.TIMELINE),
            ("Compare wallet A versus wallet B risk", QueryType.COMPARISON),
        ],
    )
    def test_classification(self, query, expected_type):
        assistant = InvestigationAssistant()
        assert assistant.classify_query(query) == expected_type

    def test_unclassifiable_query_falls_back_to_case_overview(self):
        assistant = InvestigationAssistant()
        assert assistant.classify_query("asdkjhaskjdh random gibberish") == QueryType.CASE_OVERVIEW


class TestExtractEntities:
    def test_extracts_ethereum_address(self):
        assistant = InvestigationAssistant()
        entities = assistant.extract_entities(
            "What's the risk for 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1?"
        )
        assert entities["address"] == "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1"

    def test_extracts_case_number(self):
        assistant = InvestigationAssistant()
        entities = assistant.extract_entities("Tell me about case TRX-20240115-0042")
        assert entities["case_number"] == "TRX-20240115-0042"

    def test_extracts_chain(self):
        assistant = InvestigationAssistant()
        entities = assistant.extract_entities("Any patterns on Polygon?")
        assert entities["chain"] == "Polygon"

    def test_no_entities_found_returns_empty_dict(self):
        assistant = InvestigationAssistant()
        assert assistant.extract_entities("hello there") == {}


# ---------------------------------------------------------------------------
# answer_query() paths that don't require the database (early-return branches)
# ---------------------------------------------------------------------------


class TestAnswerQueryNoDB:
    async def test_risk_summary_without_wallet_or_case_asks_for_more_info(self):
        response = await investigation_assistant.answer_query(query="how risky is this wallet")
        assert response.query_type == QueryType.RISK_SUMMARY
        assert response.confidence == ConfidenceLevel.UNKNOWN
        assert response.evidence == []

    async def test_attribution_without_wallet_or_address_asks_for_more_info(self):
        response = await investigation_assistant.answer_query(query="where did the funds go")
        assert response.query_type == QueryType.ATTRIBUTION
        assert response.confidence == ConfidenceLevel.UNKNOWN

    async def test_fund_flow_without_wallet_asks_for_more_info(self):
        response = await investigation_assistant.answer_query(query="trace the money flow")
        assert response.query_type == QueryType.FUND_FLOW
        assert response.confidence == ConfidenceLevel.UNKNOWN

    async def test_entity_lookup_without_address_asks_for_more_info(self):
        response = await investigation_assistant.answer_query(query="who owns this address")
        assert response.query_type == QueryType.ENTITY_LOOKUP
        assert response.confidence == ConfidenceLevel.UNKNOWN

    async def test_case_overview_without_case_id_asks_for_more_info(self):
        response = await investigation_assistant.answer_query(query="tell me about case status")
        assert response.query_type == QueryType.CASE_OVERVIEW
        assert response.confidence == ConfidenceLevel.UNKNOWN

    async def test_comparison_always_asks_for_two_targets(self):
        response = await investigation_assistant.answer_query(query="compare risk versus other")
        assert response.query_type == QueryType.COMPARISON
        assert "two" in response.answer.lower()

    async def test_general_fallback_lists_capabilities(self):
        response = await investigation_assistant.answer_query(query="asdkjhaskjdh")
        assert response.query_type == QueryType.CASE_OVERVIEW
        assert "risk analysis" in response.answer.lower()
        assert len(response.follow_up_questions) > 0


# ---------------------------------------------------------------------------
# HTTP endpoint tests that don't require the database
# ---------------------------------------------------------------------------


@pytest.fixture
async def plain_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestAIEndpointsNoDB:
    async def test_query_endpoint_without_case_id(self, plain_client):
        response = await plain_client.post(
            "/api/v1/ai/query", json={"query": "tell me about my investigation"}
        )
        assert response.status_code == 200
        body = response.json()
        assert "answer" in body
        assert "query_type" in body
        assert "confidence" in body

    async def test_query_endpoint_validates_empty_query(self, plain_client):
        response = await plain_client.post("/api/v1/ai/query", json={"query": ""})
        assert response.status_code == 422

    async def test_capabilities_endpoint(self, plain_client):
        response = await plain_client.get("/api/v1/ai/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert "capabilities" in body
        assert len(body["capabilities"]) >= 5
        assert "confidence_levels" in body

    async def test_capabilities_reports_mode_honestly(self, plain_client):
        """`/ai/capabilities` reports the real live/demo/disabled mode (see
        `Settings.effective_ai_mode`) rather than a fixed value - this
        sandbox has no ANTHROPIC_API_KEY, so it should honestly say "demo",
        not "live"."""
        response = await plain_client.get("/api/v1/ai/capabilities")
        body = response.json()
        assert body["mode"] in ("live", "demo", "disabled")
        assert body["mode"] == "demo"
        assert body["model"] is None

    @pytest.fixture
    async def _require_redis(self):
        """ChatSessionStore persists sessions to Redis with no in-memory
        fallback (see src/ai/api.py), so only the chat/* tests below need a
        reachable REDIS_URL. Skip cleanly rather than fail when one isn't
        available, matching fixtures_db.py's db_session skip-if-unreachable
        pattern. Not autouse: the query/capabilities tests above don't touch
        Redis and should keep running without it.

        Also resets ChatSessionStore's cached client after each test:
        pytest-asyncio gives each test function its own event loop, but
        ChatSessionStore._redis is a class-level singleton created against
        whichever loop was active when it was first used -- left cached
        across tests, the next test's loop finds a connection pool bound to
        an already-closed one ("RuntimeError: Event loop is closed"). A real
        server process only ever has one loop for its whole lifetime, so
        this reset is a test-isolation fix, not a production behavior change.
        """
        import redis.asyncio as aioredis

        from src.ai.api import ChatSessionStore
        from src.core.config import get_settings

        client = aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)
        try:
            await client.ping()
        except Exception as exc:
            pytest.skip(f"Redis not reachable: {exc}")
        finally:
            await client.aclose()

        yield

        if ChatSessionStore._redis is not None:
            await ChatSessionStore._redis.aclose()
            ChatSessionStore._redis = None

    async def test_chat_roundtrip_creates_and_retrieves_history(self, plain_client, _require_redis):
        chat_response = await plain_client.post("/api/v1/ai/chat", json={"message": "hello there"})
        assert chat_response.status_code == 200
        session_id = chat_response.json()["session_id"]
        assert chat_response.json()["message"]["role"] == "assistant"

        history_response = await plain_client.get(f"/api/v1/ai/chat/history/{session_id}")
        assert history_response.status_code == 200
        messages = history_response.json()["messages"]
        assert len(messages) == 2  # user + assistant
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    async def test_chat_history_not_found(self, plain_client, _require_redis):
        response = await plain_client.get(f"/api/v1/ai/chat/history/{uuid4()}")
        assert response.status_code == 404

    async def test_chat_history_delete(self, plain_client, _require_redis):
        chat_response = await plain_client.post("/api/v1/ai/chat", json={"message": "delete me"})
        session_id = chat_response.json()["session_id"]

        delete_response = await plain_client.delete(f"/api/v1/ai/chat/history/{session_id}")
        assert delete_response.status_code == 200

        history_response = await plain_client.get(f"/api/v1/ai/chat/history/{session_id}")
        assert history_response.status_code == 404


# ---------------------------------------------------------------------------
# HTTP endpoint tests that require the database
# ---------------------------------------------------------------------------


class TestAIEndpointsWithDB:
    async def test_query_endpoint_unknown_case_id_returns_404(self, api_client):
        response = await api_client.post(
            "/api/v1/ai/query",
            json={"query": "case summary please", "case_id": str(uuid4())},
        )
        assert response.status_code == 404

    async def test_generate_narrative_currently_raises_on_undefined_chains_variable(
        self, api_client, db_session
    ):
        """KNOWN BUG in the current `/ai/generate-narrative` implementation
        (src/api/v1/ai.py's `generate_investigation_narrative`): it appends
        a line referencing a local variable `chains` that is never assigned
        anywhere in the function, so the endpoint unconditionally raises
        `NameError` for any existing case (with or without wallets). This
        test documents today's actual (broken) behavior so it fails loudly
        if silently "fixed" by accident, and should be replaced with a
        real success assertion once WS2's narrative rewrite (or a bugfix)
        lands and defines `chains` before using it.
        """
        from src.models import Case, CaseStatus, CrimeType

        case = Case(
            case_number=f"TRX-TEST-{uuid4().hex[:6]}",
            title="Narrative Bug Case",
            crime_type=CrimeType.FRAUD,
            description="test",
            status=CaseStatus.OPEN,
        )
        db_session.add(case)
        await db_session.flush()
        await db_session.commit()

        response = await api_client.post(
            "/api/v1/ai/generate-narrative", params={"case_id": str(case.id)}
        )
        assert response.status_code == 500
