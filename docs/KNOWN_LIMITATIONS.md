# Known Limitations

> **Status:** Updated 2026-09-01 against commit history through the production-readiness pass on `main`.
> Reflects the actual merged/current codebase, not a pre-merge baseline. Superseded items are removed
> rather than left stale; see git history if that context is needed.

## AI Assistant

- **Template-fallback mode.** `apps/api/src/ai/service.py` falls back to deterministic template/regex responses
  whenever `ANTHROPIC_API_KEY` is unset, rather than calling the Claude API. This is intentional (never 500 for a
  missing key), but a deployment without a real Anthropic key gets non-AI-generated answers while still presenting
  itself as the "AI Investigation Assistant." Check `GET /ai/capabilities` for a live/template mode indicator.
- **Chat session persistence** is Redis-backed (`ChatSessionStore` in `apps/api/src/ai/api.py`), 7-day TTL. No
  fallback if Redis is unavailable — chat endpoints will error rather than degrade to in-memory.

## Blockchain Providers

- **BSC has no registered provider.** Ethereum, Polygon, Arbitrum, Optimism, and Base are all registered via
  Alchemy/Infura (see `apps/api/src/providers/factory.py`); BSC is the one CHAIN_CONFIGS entry with no provider,
  because neither Alchemy nor Infura support it and no generic-RPC provider class exists yet. Selecting BSC fails
  with "no provider for chain" at analysis time. Adding it needs either a third vendor integration or a bare
  JSON-RPC provider class pointed at an operator-supplied `BSC_RPC_URL`.
- **No real API keys are configured anywhere** (Alchemy/Infura/Chainalysis/CipherTrace) in this environment, by
  design — the code is env-driven and falls back to `ProviderNotConfiguredError`/empty results rather than crashing,
  but zero live blockchain data will flow until an operator supplies real keys.

## Authentication & Sessions

- **Frontend token storage.** `apps/web/src/store/auth-store.ts` persists access/refresh tokens to `localStorage`
  via Zustand's `persist` middleware (documented as a known limitation directly in that file). This is readable by
  any script that can execute in the page's origin — i.e. vulnerable to token exfiltration via XSS. Treat it as an
  accepted trade-off requiring strong XSS hygiene elsewhere (CSP headers, output encoding, dependency hygiene)
  rather than a defense in itself. An httpOnly-cookie-based session would avoid this class of risk entirely, but
  it's a real architectural change (server-side cookie issuance/refresh, CSRF protection, a breaking API-contract
  change for any direct/non-browser client) — worth a deliberate decision, not a silent rewrite.

## Celery / Background Tasks

- **A `beat` process is required alongside `worker`** for `cleanup_stale_investigations` (hourly) and
  `periodic_entity_sync` (every 6h) to actually fire — both are now provisioned as separate services in both
  `docker-compose.yml` and `docker-compose.prod.yml`. If you run the worker outside these compose files (bare
  metal, a different orchestrator), remember beat is a distinct process: `celery -A src.workers.main.celery_app
  beat`.

## Infrastructure / Monitoring

- **Neo4j metrics aren't scraped.** Postgres and Redis now have exporters (`postgres-exporter`, `redis-exporter`
  services + matching Prometheus scrape jobs); Neo4j's own built-in Prometheus metrics endpoint isn't enabled
  (`server.metrics.prometheus.enabled=true` + exposing its port), so the dashboard's Neo4j heap-usage panel has no
  data behind it yet.
- **nginx/container-level metrics aren't collected.** `nginx-exporter`/`cadvisor`/`node-exporter` from an earlier
  draft of the Prometheus config were never deployed as services; the "System Memory Usage" panel on the Grafana
  dashboard has no data behind it without `node-exporter` specifically.

## Settings Page / User Management

- **No role/status change reason or audit trail in the UI.** `PATCH /auth/users/{id}` (activate/deactivate, change
  role) exists and the Users tab's status badge is now a working toggle, but there's no confirmation dialog or
  visible history of who changed what — the change lands in the `audit_log` table (`AuditAction.USER_UPDATE`) but
  isn't surfaced anywhere in the UI.

## Docker / Deployment

- **No full image build was verified**, only `docker compose config` (both compose files parse and validate
  correctly per the green "Docker Compose Validation" CI workflow). A real `docker build` of
  `apps/api/Dockerfile.prod` / `apps/web`'s Dockerfile, and a full `docker compose up` smoke test, have not been run
  in this environment (no Docker CLI available in this sandbox) — do that before a first real deploy. In particular,
  verify the `worker`/`beat` services actually come up: their command was previously broken (`python -m
  src.workers.main` doesn't start anything — fixed to the real `celery ... worker`/`celery ... beat` invocation) and
  that specific failure mode couldn't be caught without a live Celery+Redis connection, only reasoned about from the
  code.
- **`docker-compose.prod.yml` env vars have no committed defaults for secrets** (`SECRET_KEY`, `POSTGRES_PASSWORD`,
  `NEO4J_PASSWORD`, `CORS_ORIGINS`, `GRAFANA_ADMIN_PASSWORD`) by design — a deploy without a populated `.env` starts
  containers with empty/invalid credentials rather than a weak-but-functional default. The compose file alone is
  not "ready to run" without an operator supplying real values first.
