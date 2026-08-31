# Known Limitations

> **Status:** Written as part of WS8 (Infra/CI/Docs), against the pre-parallel-merge baseline plus this workstream's
> own changes. Some items below describe design choices made by other workstreams (WS1–WS7) that this workstream's
> worktree cannot directly inspect — those are noted generically, based on the project plan's stated intent, and
> should be corrected if the merged implementation differs.

## AI Assistant

- **Template-fallback mode.** The AI investigation assistant (`apps/api/src/ai/service.py`) is designed to fall back
  to its original template/regex-based response logic whenever `ANTHROPIC_API_KEY` is not set in the environment,
  rather than calling the Claude API. This is intentional (never return a 500 for a missing key), but it means any
  deployment without a real Anthropic key gets non-AI-generated, templated answers while still presenting itself as
  the "AI Investigation Assistant." Check `GET /ai/capabilities` for a live/template mode indicator once WS2 lands.
- **Chat session persistence.** In the baseline tree, `ChatSessionStore` in `apps/api/src/ai/api.py` is an in-process
  Python dict — chat history is lost on restart and does not survive across multiple worker processes/replicas. WS2's
  design intent is to move this to Redis; confirm this landed before relying on multi-worker chat continuity in
  production.
- **`generate-narrative` has a latent bug.** `apps/api/src/ai/api.py::generate_investigation_narrative` references an
  undefined local variable `chains` in its cross-chain-activity summary line — this raises `NameError` at runtime
  whenever the target case has any wallets. Needs a fix (trivial: `chains = list(set(w.chain for w in wallets))`)
  wherever this endpoint's owning workstream (WS2) lands.

## Blockchain Providers

- **"Not configured" behavior.** When `ALCHEMY_API_KEY`/`INFURA_API_KEY`/`CHAINALYSIS_API_KEY`/`CIPHERTRACE_API_KEY`
  are absent, `ProviderFactory.initialize()` simply does not register a provider for the affected chain(s)/services.
  Code paths that need a provider and don't find one currently raise a generic `ValidationError` (see
  `apps/api/src/services/wallet_analysis.py`) rather than a purpose-built exception. WS3 introduces
  `ProviderNotConfiguredError` for this case — until that lands (and until `chainalysis.py`/`ciphertrace.py` exist),
  any wallet analysis or entity-enrichment flow that depends on those services will behave as if the feature simply
  isn't there, with no explicit user-facing message pointing at the missing key.
- **Infura provider is partially stubbed.** `apps/api/src/providers/evm/infura.py`'s `get_transactions_by_address`
  discards its own RPC call result and returns `[]`; `get_token_transfers` unconditionally returns `[]`. Any
  deployment relying on Infura as its only provider (no Alchemy key) will see zero transaction/token-transfer data
  until WS3's fix lands.
- **Only Ethereum and Polygon have registered providers**, even though `WalletAnalysisService._get_chain_id` maps
  additional chain names (BSC, Arbitrum, Optimism, Base) to chain ids. Selecting one of those unsupported chains will
  fail with "no provider for chain" at analysis time.

## Authentication & Sessions

- **Token storage (frontend).** Per the project plan, WS5 (frontend auth & shell) is expected to store access/refresh
  tokens in a client-side auth store; if that store persists to `localStorage` (a common Zustand pattern), tokens
  become readable by any script that can execute in the page's origin — i.e. vulnerable to exfiltration via XSS. This
  is a generic caveat about the design direction, not a confirmed implementation detail (WS5's actual code is not
  visible from this worktree) — verify the actual storage mechanism once WS5 merges, and if it is `localStorage`,
  treat it as an accepted trade-off requiring strong XSS hygiene elsewhere (CSP headers, output encoding, dependency
  hygiene) rather than a defense in itself. An httpOnly-cookie-based session would avoid this class of risk entirely
  but was not the path this plan committed to.
- **No `/auth/logout` in baseline.** `AuditAction.LOGOUT` exists in the audit-log action enum but is never referenced
  by any endpoint in the baseline tree — there is no way to invalidate a token before its natural expiry. WS1 adds
  logout with JTI-based Redis blacklisting.
- **`SECRET_KEY` insecure default.** Baseline `core/config.py` defaults `SECRET_KEY` to
  `secrets.token_urlsafe(32)` generated fresh at import time — meaning every process restart invalidates all
  previously-issued tokens, and a multi-worker deployment without an explicit `SECRET_KEY` env var would have each
  worker minting/validating tokens with a *different* key, breaking auth non-deterministically. WS1 removes this
  default and requires the value from environment in production.

## Celery / Background Tasks

- **Analysis and report endpoints run inline (baseline), not via Celery.** `POST /analysis/cases/{case_id}/wallets/
  analyze`, `POST /analysis/wallets/{wallet_id}/trace`, and `POST /risk/reports/generate` all call their respective
  service functions synchronously and block the HTTP request until completion, even though `wallet_analysis_task`,
  `report_generation_task`, `graph_sync_task`, and `entity_enrichment_task` are already defined as Celery
  `shared_task`s in `apps/api/src/workers/tasks.py`. WS3 rewires the endpoints to `.delay()` these tasks and return a
  task id instead.
- **`graph_sync_task` and `entity_enrichment_task` appear unwired.** No API endpoint or other code path calling
  `.delay()` on either task was found in the baseline tree — the only enrichment/sync calls found are synchronous,
  inline calls to the underlying service functions from within the analysis/graph endpoints themselves. Treat these
  two tasks as periodic-only/unwired until confirmed otherwise in the merged tree.
- **`cleanup_stale_investigations` has no confirmed periodic trigger.** The task exists (marks `RUNNING` investigations
  stale after 24h), but no Celery beat schedule registering it was found in `apps/api/src/workers/main.py` at
  baseline. If no beat schedule exists, investigations that error without hitting the code's own `except` branch
  (e.g. a worker crash mid-task) could stay `RUNNING` indefinitely.

## Reports

- **The `src/reports` module does not exist in baseline** (see `docs/contracts/report-schema.md` for the full
  breakdown) — both `apps/api/src/api/v1/risk.py` and `apps/api/src/workers/tasks.py` import
  `from src.reports import report_generator, ReportFormat, ReportTemplate`, which will raise `ModuleNotFoundError`
  until WS3 adds it. Until then, the FastAPI app likely fails to start at all (the `risk` router is presumably
  imported at app startup).
- **PDF report download is a hardcoded stub.** `GET /risk/reports/{id}/download` returns a fixed placeholder byte
  string regardless of the report's declared format — a "PDF" download today would not start with `%PDF-` magic
  bytes. WS3 adds real rendering.

## Infrastructure / Monitoring (this workstream's own scope)

- **Prometheus exporters trimmed, not implemented.** The original `docker/prometheus/prometheus.yml` referenced
  `postgres-exporter`, `redis-exporter`, `nginx-exporter`, `cadvisor`, and `node-exporter` as scrape targets, but none
  of these are defined as services in either `docker/docker-compose.yml` or `docker/docker-compose.prod.yml`. This
  workstream trimmed `scrape_configs` down to targets that actually exist (`prometheus` self-scrape,
  `tracex-backend`, `tracex-frontend`) rather than half-wiring new exporter services without corresponding compose
  entries. **Future work:** add `postgres_exporter`, `redis_exporter`, and (if nginx metrics are wanted)
  `nginx-prometheus-exporter` as real services to `docker-compose.prod.yml`, plus re-add their scrape jobs.
- **Backend `/api/v1/metrics` endpoint does not exist yet.** The `tracex-backend` Prometheus scrape target in
  `prometheus.yml` points at `metrics_path: /api/v1/metrics`, but no such route was found under
  `apps/api/src/api/v1/`. The new `docker/prometheus/rules/alerts.yml` alert rules for error rate and latency
  (`HighErrorRate`, `HighLatency`) depend on `http_requests_total`/`http_request_duration_seconds_bucket` metrics
  that this endpoint would need to expose (e.g. via `prometheus-fastapi-instrumentator` or similar) — until that
  exists, those two alert rules will simply never fire (no data), which is safer than a false negative but is not the
  same as working monitoring. The `ServiceDown` (`up == 0`) rule works today against any of the three currently
  scraped jobs.
- **No Grafana dashboards provisioned.** `docker-compose.prod.yml` mounts `./grafana/dashboards` and
  `./grafana/datasources`, but this workstream did not find pre-built dashboard JSON under `docker/grafana/` — Grafana
  will come up with no dashboards until some are added.

## Settings Page / User Management

- Per the project plan's WS6 section, if the backend has no dedicated user-management endpoint by the time WS6 wires
  up the settings page, WS6 is instructed not to invent one and to leave `mockUsers` removed but unreplaced,
  documenting the gap here. This workstream cannot directly confirm from its own worktree whether such an endpoint
  exists post-merge (`apps/api/src/api/v1/auth.py`'s baseline surface has `POST /auth/users` for admin-only user
  creation, but no `GET /auth/users` list/list-and-edit endpoint was found in the baseline tree). If WS6 landed
  without a real user-list endpoint, the settings page's "Users" tab is expected to be non-functional or removed —
  verify against the merged frontend before demoing that tab.

## Docker / Deployment

- **No clean-environment verification was performed by this workstream.** The sandbox this workstream ran in has no
  `docker` CLI available, so `docker compose -f docker/docker-compose.prod.yml config` (and the dev equivalent) could
  only be checked via YAML-syntax parsing (`yaml.safe_load`), not full Compose-spec validation (variable
  interpolation, schema validation against the Compose spec, image reference validation). Re-run the actual
  `docker compose config` command in an environment with Docker installed before treating this as fully verified —
  see `docs/FINAL_TEST_REPORT.md`.
- **`docker/docker-compose.prod.yml` env vars have no committed defaults for secrets** (`SECRET_KEY`,
  `POSTGRES_PASSWORD`, `NEO4J_PASSWORD`, `CORS_ORIGINS`, `GRAFANA_ADMIN_PASSWORD`) by design — a production deploy
  without a populated `.env` will start containers with empty/invalid credentials rather than falling back to a
  weak-but-functional default. This is the intended trade-off (no committed weak secrets) but means the compose file
  alone is not "ready to run" without an operator supplying real values first.
