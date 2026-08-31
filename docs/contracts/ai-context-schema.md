# AI Assistant Context Schema

> **Status:** Baseline reference (pre-parallel-merge). Derived from `apps/api/src/ai/schemas.py`, `apps/api/src/ai/api.py`.
> `apps/api/src/ai/service.py` (the actual query-handling logic) was not fully read line-by-line for this doc pass, but
> its **behavior mode** is confirmed from `docs/FEATURE_REALITY_MATRIX.md`/`ARCHITECTURE_GAP_ANALYSIS.md` and cross-checked
> against `ai/api.py`'s call sites.
> **This doc is the most likely to go stale of the ten contract docs** — WS2 replaces the template dispatch in
> `ai/service.py` with real Claude calls (falling back to templates when `ANTHROPIC_API_KEY` is unset), and moves
> `ChatSessionStore` off the in-memory dict onto Redis. Re-verify the `/ai/capabilities` payload and any new
> `ANTHROPIC_*` config fields once WS2 lands.

## `QueryType` (8 types)

```
RISK_SUMMARY, ATTRIBUTION, PATTERN_DETECTION, FUND_FLOW,
ENTITY_LOOKUP, CASE_OVERVIEW, TIMELINE, COMPARISON
```
`investigation_assistant.answer_query` (in `ai/service.py`) classifies incoming natural-language queries into one of
these 8 types — baseline behavior is regex/keyword dispatch (`classify_query`), not an LLM call.

## `ConfidenceLevel` (ai module's own copy)

Same 4 values as elsewhere (`CONFIRMED`, `HIGH_CONFIDENCE`, `PROBABLE`, `UNKNOWN`) — yet another independent
definition of this enum (see `graph-schema.md`'s note on this pattern repeating across modules).

## `Evidence`

```python
source: str
evidence_type: str
description: str
confidence: ConfidenceLevel
data: dict
timestamp: datetime
```
Each `AIQueryResponse` carries a list of these — the "evidence grounding" mechanism referenced in the audit docs.
Baseline evidence is assembled from the same graph/risk/attribution query results documented in
`graph-schema.md`/`risk-schema.md`/`attribution-schema.md`, formatted into `Evidence` objects by the relevant
`_handle_*` method in `ai/service.py`.

## Request/response contracts

```python
class AIQueryRequest(BaseModel):
    query: str          # 1-2000 chars
    case_id: str | None
    wallet_id: str | None

class AIQueryResponse(BaseModel):
    answer: str
    query_type: QueryType
    confidence: ConfidenceLevel
    evidence: list[Evidence]
    follow_up_questions: list[str]
    metadata: dict
```

```python
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    metadata: dict

class ChatSession(BaseModel):
    session_id: str
    case_id: str | None
    messages: list[ChatMessage]
    created_at / updated_at: datetime

class ChatRequest(BaseModel):
    message: str          # 1-2000 chars
    session_id: str | None
    case_id: str | None
    wallet_id: str | None

class ChatResponse(BaseModel):
    session_id: str
    message: ChatMessage           # the assistant's reply
    suggested_actions: list[str]   # top-3 follow_up_questions from the underlying AIQueryResponse
```

## Session storage (baseline)

`ChatSessionStore` in `ai/api.py` is a **class-level Python dict** (`_sessions: Dict[str, ChatSession] = {}`) — in-process
memory only. This means:
- Chat history is lost on every backend restart/redeploy.
- With multiple Uvicorn/Gunicorn workers or replicas, a session's messages can land on a different worker than the one
  that created it, appearing to "lose" history mid-conversation.

WS2 is expected to move this to Redis-backed storage. Until then, this is a documented limitation
(see `docs/KNOWN_LIMITATIONS.md`).

## `/ai/capabilities` (static catalog)

Returns a fixed JSON structure (not derived from `service.py` logic) describing the 7 documented capability areas
(Risk Analysis, VASP Attribution, Pattern Detection, Fund Flow Tracing, Entity Intelligence, Case Overview, Timeline
Analysis) plus the 4 confidence levels and their meanings. WS2's task list calls for this endpoint to "report
live-vs-template mode honestly" — as of baseline it does not distinguish live-LLM mode from template mode at all
(no such field exists in the response). Re-check for a `mode: "live" | "template"`-style field post-merge.

## Narrative generation (`POST /ai/generate-narrative`)

Baseline implementation (`ai/api.py::generate_investigation_narrative`) builds a markdown report by string-formatting
case/wallet/investigation data directly — no LLM call. **Bug found while reading this endpoint:** the function
references a local variable `chains` (`f"...across {len(chains)} chains: {', '.join(chains)}"`) that is never defined
anywhere in the function body — this line will raise `NameError` at runtime if reached (i.e. whenever any wallets
exist for the case). Flagged for whichever workstream owns `ai/api.py` post-merge (WS2, per the ownership table) to
fix alongside the Claude integration work; also noted in `docs/KNOWN_LIMITATIONS.md`.

## Env vars

`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` do not exist in `core/config.py` as of baseline — WS2 adds them. Absent a key,
WS2's design intent (per the project plan) is graceful degrade to the current template logic, never a 500.
