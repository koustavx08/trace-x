# TRACE-X API Contract

> **Status:** Baseline reference, written from the pre-parallel-merge repo state (commit `4dd2c6e`, before WS1–WS7 land).
> Derived directly from `apps/api/src/api/v1/*.py`, `apps/api/src/schemas/__init__.py`, and `apps/api/src/ai/schemas.py`.
> **Caveat:** WS1 (auth hardening), WS2 (Claude AI), and WS3 (reports/providers/Celery) change several of these endpoints'
> internal behavior (and add `/auth/logout`). Endpoint paths and request/response shapes documented here should still hold,
> but re-verify against the merged code before treating this as authoritative for anything touching auth, AI, or reports/Celery task IDs.

All endpoints are mounted under the API prefix `/api/v1` (see `API_V1_PREFIX` in `src/core/config.py`).

## Conventions

- All IDs are UUIDv4 strings.
- Timestamps are ISO-8601 strings (UTC).
- Paginated list endpoints return `PaginatedResponse<T>`: `{ items: T[], total, page, page_size, total_pages }`.
- Errors: `NotFoundError` → 404, `ValidationError` → 400 (see `src/core/exceptions.py`). No standardized error envelope was found beyond FastAPI's default `{"detail": ...}`.

---

## Health — `src/api/v1/health.py`

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Full health check (`HealthResponse`: status, version, timestamp, services) |
| GET | `/health/ready` | Readiness probe |
| GET | `/health/live` | Liveness probe (used by `docker-compose.prod.yml` backend healthcheck) |

## Auth — `src/api/v1/auth.py`

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/login` | none | `LoginRequest` → `TokenResponse` (access + refresh tokens) |
| POST | `/auth/refresh` | none | body/query `refresh_token: str` → `TokenResponse` |
| GET | `/auth/me` | Bearer | Current user → `UserResponse` |
| POST | `/auth/users` | Bearer (admin) | Create user (admin-only, `require_admin` dependency) |
| POST | `/auth/change-password` | Bearer | Change own password |

**Gap (as of baseline):** no `/auth/logout` endpoint exists yet. `AuditAction.LOGOUT` is defined but unused. WS1 is expected to add
logout with JTI-based Redis blacklisting — verify against merged `src/api/v1/auth.py` / `src/auth/__init__.py`.

## Cases — `src/api/v1/cases.py`

Standard CRUD (`POST/GET/PATCH/DELETE /cases`, `GET /cases/{id}`) over `CaseCreate` / `CaseUpdate` / `CaseResponse` (see `domain-model.md`).

## Wallets — `src/api/v1/wallets.py`

Standard CRUD (`POST/GET/PATCH/DELETE /wallets`, `GET /wallets/{id}`) over `WalletCreate` / `WalletUpdate` / `WalletResponse`.

## Investigations — `src/api/v1/investigations.py`

CRUD-style endpoints over `InvestigationRunCreate` / `InvestigationRunUpdate` / `InvestigationRunResponse`. See `investigation-state-machine.md` for the status lifecycle.

## Analysis — `src/api/v1/analysis.py` (prefix `/analysis`)

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/analysis/wallets/validate` | query `address`, `chain_id?` | `{valid, address, chain_id, chain_name, ...}` |
| POST | `/analysis/cases/{case_id}/wallets/analyze` | `WalletAnalyzeRequest{address, chain_id?, label?, trace_depth, max_transactions}` | `WalletAnalyzeResponse{wallet, investigation}` |
| POST | `/analysis/wallets/{wallet_id}/trace` | `TraceRequest{max_hops, min_value_eth}` | fund-flow trace dict (`root_address, wallets_traced, edges[], paths[], max_hops_reached`) |
| GET | `/analysis/wallets/{wallet_id}/transactions` | `page, page_size` | paginated transaction list |
| GET | `/analysis/chains` | — | supported chains |

**Baseline behavior:** `analyze_wallet_in_case` and `trace_fund_flow` call `wallet_analysis_service` **synchronously inline**, not via Celery
`.delay()` — the request blocks until analysis completes. WS3 is expected to change this to return a task id immediately
(`wallet_analysis_task.delay(...)`). Re-verify response shape once that lands (a task id response would replace `WalletAnalyzeResponse`).

## Graph — `src/api/v1/graph.py` (prefix `/graph`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/graph/wallets/sync` | Push a Postgres wallet + its transactions into Neo4j |
| POST | `/graph/subgraph` | `SubgraphRequest{addresses[], chain, depth}` → subgraph nodes/edges |
| POST | `/graph/wallets/{wallet_id}/paths-to-vasp` | Shortest paths to exchange/bridge entities |
| POST | `/graph/wallets/{wallet_id}/mixer-check` | Mixer interaction check |
| POST | `/graph/patterns/detect` | `PatternDetectionRequest{chain, pattern_type, time_window_hours}` — `peel_chain\|round_amount\|rapid_movement\|mixer` |
| POST | `/graph/clusters/detect` | `ClusterDetectionRequest{chain, min_cluster_size}` |
| GET | `/graph/wallets/{wallet_id}/stats` | Wallet graph stats |
| GET | `/graph/wallets/{wallet_id}/centrality` | `algorithm=pagerank\|betweenness\|degree` |
| GET | `/graph/wallets/{wallet_id}/temporal-flow` | `start_date, end_date, bucket=hour\|day\|week` |
| POST | `/graph/entities/lookup` | `EntityLookupRequest{address, chain}` |
| POST | `/graph/entities/enrich` | Enrich a wallet with entity intelligence |
| POST | `/graph/entities/sync` | Sync entity registry to Neo4j |
| GET | `/graph/health` | Neo4j connectivity check |

See `graph-schema.md` for the underlying node/relationship model.

## Risk — `src/api/v1/risk.py` (prefix `/risk`)

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/risk/wallets/{wallet_id}/assess` | — | `RiskAssessmentResponse` (see `risk-schema.md`) |
| GET | `/risk/wallets/{wallet_id}/attribution` | `max_hops?` | `AttributionResponse` (see `attribution-schema.md`) |
| POST | `/risk/wallets/{wallet_id}/attribute` | `max_hops?` | `List[VASPAttribution dict]` |
| POST | `/risk/reports/generate` | `ReportGenerateRequest{case_id, investigation_run_id?, title?, template, format, generated_by}` | `ReportGenerateResponse{report_id, title, format, file_size, generated_at}` |
| GET | `/risk/reports/{report_id}/download` | — | binary/blob (see `report-schema.md` for the current stub caveat) |
| GET | `/risk/cases/{case_id}/risk-summary` | — | case-level risk distribution summary |

**Known blocker (baseline):** `src/api/v1/risk.py` and `src/workers/tasks.py` both `from src.reports import report_generator, ReportFormat,
ReportTemplate`, but no `apps/api/src/reports/` module exists in the baseline tree. This is a broken import — the app will fail to start
until WS3 adds `apps/api/src/reports/generator.py`. Track in `docs/PRODUCTION_READINESS.md`.

## Reports — `src/api/v1/reports.py` (prefix `/reports`)

Separate, simpler CRUD surface over the `Report` DB model directly (`POST/GET /reports`, `GET /reports/{id}`) — distinct from
`/risk/reports/generate`, which drives actual document generation via `report_generator`. Both write to the same `reports` table.

## Reports (report content generation) — see `report-schema.md`

## AI — `src/ai/api.py` (prefix `/ai`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/ai/query` | `AIQueryRequest{query, case_id?, wallet_id?}` → `AIQueryResponse{answer, query_type, confidence, evidence[], follow_up_questions[], metadata}` |
| POST | `/ai/chat` | `ChatRequest{message, session_id?, case_id?, wallet_id?}` → `ChatResponse{session_id, message, suggested_actions[]}` |
| GET | `/ai/chat/history/{session_id}` | Chat transcript |
| DELETE | `/ai/chat/history/{session_id}` | Clear chat session |
| GET | `/ai/capabilities` | Static capability/confidence-level catalog |
| POST | `/ai/generate-narrative` | `case_id, wallet_ids?` → markdown narrative string |

**Baseline behavior:** `investigation_assistant.answer_query` in `src/ai/service.py` is template/regex-dispatch based (no LLM call), and
`ChatSessionStore._sessions` is an in-memory class-level dict (lost on restart, not shared across workers). `generate-narrative` builds its
markdown via Python f-strings over case/wallet/investigation data, not an LLM call. WS2 replaces the template dispatch with real Claude calls
(falling back to templates when `ANTHROPIC_API_KEY` is unset) and moves chat sessions to Redis — re-verify request/response shapes still
hold (they're designed to be additive, not breaking) once WS2 lands. See `ai-context-schema.md`.

---

## Shared response envelopes

- `PaginatedResponse<T>` — see Conventions above.
- `HealthResponse` — `{status, version, timestamp, services: {database, neo4j, redis}}` in `packages/shared/src/index.ts`; backend's
  `src/schemas/__init__.py::HealthResponse` is looser (`services: dict`).
