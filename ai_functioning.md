# TRACE-X AI Assistant Architecture & Functioning

## 1. Overview & Purpose
The TRACE-X AI Assistant is an **AI-powered Blockchain Financial Crimes Copilot** designed for forensic investigators, compliance officers, and law enforcement. 

It translates raw, multi-hop blockchain data, graph relationships, transaction patterns, heuristics, and risk engine scores into natural-language answers and structured forensic evidence.

---

## 2. Core Operational Modes (`AI_MODE`)
The assistant operates in one of three modes (configured in `apps/api/src/core/config.py`):

1. **`live`**:
   - Connects to a live external LLM API (Anthropic or OpenRouter).
   - Uses LLM for structured intent classification, entity extraction, and natural-language answer composition.
2. **`demo` (Default when no API keys are provided)**:
   - **100% offline and deterministic.**
   - Uses compiled regexes to classify queries and extract entities (e.g., `0x...` addresses, `TRX-...` case numbers).
   - Formulates answers using structured templates populated with **real evidence** from the local database, risk engine, and graph repository.
   - **No external API calls are made and no API keys are required.**
3. **`disabled`**:
   - Turns off AI features while allowing the rest of TRACE-X (risk scoring, graph visualization, reports) to function normally.

> **Auto-Detection:** If `AI_MODE` is left unset, the backend checks for API keys: if an API key is present, it selects `live`; otherwise, it automatically defaults to `demo`.

---

## 3. Which AI Models & APIs Are Called?

When in `live` mode, the backend connects to either **Anthropic** or **OpenRouter** (configured via `AI_PROVIDER`):

| Provider | Setting | Default Model | Protocol & Usage |
| :--- | :--- | :--- | :--- |
| **Anthropic** (Default) | `AI_PROVIDER=anthropic` | `claude-sonnet-5` (via `ANTHROPIC_MODEL`) | Uses the official `anthropic.AsyncAnthropic` SDK.<br>• **Classification:** Anthropic Tool-Use (`classify_investigation_query`)<br>• **Answer Composition:** Messages API (`max_tokens: 1024`)<br>• **Narratives:** Messages API (`max_tokens: 2048`) |
| **OpenRouter** | `AI_PROVIDER=openrouter` | Configured via `OPENROUTER_MODEL` (e.g. `google/gemini-2.0-flash-001`, `meta-llama/llama-3.3-70b-instruct`, `anthropic/claude-3.5-sonnet`) | Uses `httpx.AsyncClient` pointing to `https://openrouter.ai/api/v1/chat/completions`.<br>• OpenAI-compatible JSON completions.<br>• Allows routing to Gemini, Llama, Claude, Mistral, or GPT models. |

---

## 4. Multi-Tier Graceful Degradation (Fail-Safe Design)
The AI service is designed with resilience so that no investigator ever sees an HTTP 500 error:

```
[User Query]
      │
      ▼
Is AI_PROVIDER OpenRouter? ──(Fails)──► Fallback to AnthropicProvider
      │ (OK)                                    │ (Fails)
      ▼                                         ▼
Call OpenRouter API                     Fallback to DeterministicDemoProvider
      │                                         │
      ├─► Success: Return LLM Answer            └─► Returns Template Answer over Real Data
      └─► API Error: Flag as "degraded", return Template Answer
```

If an external LLM call fails, times out, or has an invalid API key:
- It records `last_error` and sets `degraded: true` in `GET /ai/capabilities`.
- It silently falls back to the deterministic answer template populated with real data.
- **The user still receives an accurate, evidence-backed answer.**

---

## 5. Supported Investigation Query Types
The service (`apps/api/src/ai/service.py`) routes queries into 8 specialized forensic analysis engines:

1. **`RISK_SUMMARY`** (`_handle_risk_summary`):
   - Analyzes wallet or case risk scores using `risk_scoring_engine`.
   - Breaks down weighted factors: OFAC sanctions, mixer interactions, darknet associations, high-velocity transactions, smart contract risks.
2. **`ATTRIBUTION`** (`_handle_attribution`):
   - Queries `attribution_engine` to trace fund flows to the nearest **VASP** (Virtual Asset Service Provider / centralized exchange like Binance, Coinbase, Kraken).
   - Computes attribution confidence: `CONFIRMED`, `HIGH_CONFIDENCE`, `PROBABLE`, or `UNKNOWN`.
3. **`PATTERN_DETECTION`** (`_handle_pattern_detection`):
   - Detects money laundering typologies:
     - **Peel chains**: Sequential hops peeling off smaller amounts.
     - **Structuring / Smurfing**: Breaking down large transfers into smaller ones to avoid detection.
     - **Mixer hops**: Interactions with mixing services like Tornado Cash.
     - **Rapid movement**: Transactions moving across hops within minutes.
4. **`FUND_FLOW`** (`_handle_fund_flow`):
   - Graph path traversal via `graph_repository` and `graph_queries`.
   - Maps multi-hop shortest paths and transaction volume from a suspect wallet to cash-out points.
5. **`ENTITY_LOOKUP`** (`_handle_entity_lookup`):
   - Identifies whether an address belongs to a known exchange, bridge, DeFi protocol, mixer, or sanctioned entity.
6. **`CASE_OVERVIEW`** (`_handle_case_overview`):
   - Aggregates case progress: total wallets, high-risk wallets, completed investigations, cross-chain footprint, and status.
7. **`TIMELINE`** (`_handle_timeline`):
   - Generates temporal sequence of transactions, identifying first-seen, last-seen, and peak activity periods.
8. **`COMPARISON`** (`_handle_comparison`):
   - Side-by-side comparison of two or more wallets or cases in terms of risk, volume, and entity connections.

---

## 6. Backend API Endpoints (`apps/api/src/ai/api.py`)

All endpoints are served under `/api/v1/ai`:

| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/ai/query` | Single-turn analytical query with confidence level, structured evidence list, and follow-up prompts. |
| `POST` | `/ai/chat` | Multi-turn chat with conversation memory stored in **Redis** (`ai:chat_session:{id}` with 7-day TTL). |
| `GET` | `/ai/chat/history/{session_id}` | Retrieves full chat history for a session from Redis. |
| `DELETE` | `/ai/chat/history/{session_id}` | Clears session history from Redis. |
| `GET` | `/ai/capabilities` | Returns active provider, model name, operational mode (`live`/`demo`/`disabled`), and whether the service is running in `degraded` state. |
| `POST` | `/ai/generate-narrative` | Generates a complete, publication-ready investigation narrative report with Executive Summary, Wallet Breakdown, Findings, and Legal Action Recommendations. |

---

## 7. Structure of an AI Response
Every response returned by the backend includes verifiable on-chain/database evidence:

```json
{
  "answer": "Wallet 0xa241... has an overall risk score of 84.5/100 (CRITICAL)...",
  "query_type": "RISK_SUMMARY",
  "confidence": "HIGH_CONFIDENCE",
  "evidence": [
    {
      "source": "risk_engine",
      "evidence_type": "weighted_factor_analysis",
      "description": "Analyzed 6 risk factors with confidence-weighted scoring",
      "confidence": "HIGH_CONFIDENCE",
      "data": { "overall_score": 84.5, "risk_level": "critical" }
    }
  ],
  "follow_up_questions": [
    "What specific risk factors contributed most to this score?",
    "Show me the attribution analysis for this wallet."
  ],
  "metadata": {
    "mode": "live"
  }
}
```

---

## 8. Frontend Integration
The Next.js frontend (`apps/web/src/app/(dashboard)/ai/page.tsx`) provides:
- **Interactive Chat Interface**: Displays user queries, AI explanations, and suggested action chips.
- **Evidence Collapsible Drawers**: Investigators can inspect the exact underlying evidence objects for transparency and legal auditing.
- **Status Indicator**: Shows whether the assistant is currently running in Live LLM mode or Demo Template mode.
