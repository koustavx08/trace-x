# Known Limitations

> **Status:** Updated 2026-09-01 against commit history through the production-readiness pass on `main`.
> Reflects the actual merged/current codebase, not a pre-merge baseline. Superseded items from the original
> WS0–WS8 audit have been removed rather than left stale; see git history if that context is needed.

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
  rather than a defense in itself. An httpOnly-cookie-based session would avoid this class of risk entirely but is
  a real architectural change (server-side cookie issuance/refresh), not a quick fix.

## Celery / Background Tasks

- **`cleanup_stale_investigations` and `periodic_entity_sync`** now run on a Celery beat schedule (hourly and every
  6 hours respectively — see `apps/api/src/workers/main.py`). This requires a Celery **beat** process running
  alongside the worker (`celery -A src.workers.main beat`) in addition to the worker itself; if only the worker is
  deployed (no beat process), these periodic tasks silently never fire. Verify both processes are provisioned in
  whatever deploys `docker-compose.prod.yml`'s `worker` service.

## Infrastructure / Monitoring

- **No Grafana dashboards provisioned.** `docker-compose.prod.yml` mounts `./grafana/dashboards` and
  `./grafana/datasources`, but no dashboard JSON exists under `docker/grafana/` yet — Grafana comes up with no
  dashboards until some are added. The `/api/v1/metrics` endpoint (see below) now gives it real data to visualize
  once dashboards are built.
- **No `postgres_exporter`/`redis_exporter`.** `docker/prometheus/prometheus.yml`'s scrape targets are limited to
  `prometheus` (self), `tracex-backend`, and `tracex-frontend` (the last one only if Next.js is ever instrumented —
  it isn't currently). Postgres/Redis-level metrics (connection pool exhaustion, replication lag, etc.) aren't
  collected; add the exporters as services plus matching scrape jobs if that visibility is needed.

## Settings Page / User Management

- **No edit/deactivate UI.** The Users tab lists real accounts and has a working "Add User" dialog
  (`POST /auth/users`), but there's no way to edit a user or deactivate an account from the frontend yet — the
  backend has no `PATCH /auth/users/{id}` (or similar) endpoint at all, so this would need a new backend route
  first, not just a frontend form.

## Docker / Deployment

- **No full image build was verified**, only `docker compose config` (both compose files parse and validate
  correctly per the green "Docker Compose Validation" CI workflow). A real `docker build` of
  `apps/api/Dockerfile.prod` / `apps/web`'s Dockerfile, and a full `docker compose up` smoke test, have not been run
  in this environment (no Docker CLI available in this sandbox) — do that before a first real deploy.
- **`docker-compose.prod.yml` env vars have no committed defaults for secrets** (`SECRET_KEY`, `POSTGRES_PASSWORD`,
  `NEO4J_PASSWORD`, `CORS_ORIGINS`, `GRAFANA_ADMIN_PASSWORD`) by design — a deploy without a populated `.env` starts
  containers with empty/invalid credentials rather than a weak-but-functional default. The compose file alone is
  not "ready to run" without an operator supplying real values first.
