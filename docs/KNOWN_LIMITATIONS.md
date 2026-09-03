# Known Limitations

> **Status:** Updated 2026-09-01 against commit history through the production-readiness pass on `main`.
> Reflects the actual merged/current codebase, not a pre-merge baseline. Superseded items are removed
> rather than left stale; see git history if that context is needed.

## AI Assistant

- **Three explicit modes.** `AI_MODE=live|demo|disabled` (see `apps/api/src/core/config.py`'s `effective_ai_mode`)
  controls `apps/api/src/ai/service.py`. Left unset, it auto-selects `live` when `ANTHROPIC_API_KEY` is present,
  else `demo`. `demo` always returns deterministic, evidence-grounded template answers over real data (never a
  fabricated transaction/ownership/VASP claim); `disabled` returns a clear "AI assistance is unavailable" message
  without touching the database at all, while the rest of the platform is unaffected. `GET /ai/capabilities` reports
  the real mode honestly (`"mode": "live"|"demo"|"disabled"`).
- **Chat session persistence** is Redis-backed (`ChatSessionStore` in `apps/api/src/ai/api.py`), 7-day TTL. No
  fallback if Redis is unavailable — chat endpoints will error rather than degrade to in-memory.

## Blockchain Providers

- **No real API keys are configured anywhere** (Alchemy/Infura/Chainalysis/CipherTrace) in this environment, by
  design — the code is env-driven and falls back to `ProviderNotConfiguredError`/empty results rather than crashing,
  but zero live blockchain data will flow until an operator supplies real keys. This includes BSC now too: it has no
  vendor API key (neither Alchemy nor Infura support that chain), only a plain `BSC_RPC_URL` an operator can point
  at any JSON-RPC endpoint (a public node, or a BSC-specific vendor like Ankr/QuickNode). See
  `docs/EXTERNAL_SERVICES_SETUP.md` for exactly how to obtain each key and what degrades without it, and
  `docs/PRODUCTION_ACCEPTANCE_REPORT.md` for what has and hasn't been verified against a live provider.

## Authentication & Sessions

- **Access/refresh tokens are httpOnly cookies now**, not localStorage. `POST /auth/login` and `/auth/refresh` set
  them (`apps/api/src/auth/__init__.py`'s `set_auth_cookies`); the frontend (`store/auth-store.ts`, `lib/api.ts`)
  never sees the token values, closing the XSS token-theft exposure that existed before. `Authorization: Bearer`
  still works too (`get_current_user` accepts either) for non-browser API clients. This relies on frontend and
  backend sharing a host in production — true here because `docker/nginx/nginx.conf` fronts both under one domain
  (`/api/*` proxied to the backend, everything else to the frontend) — a different deploy topology (separate
  subdomains, no shared reverse proxy) would need an explicit cookie `Domain=` and likely a CORS/SameSite review
  before this still works.
- **CSRF protection is SameSite=Lax only**, not a separate CSRF token. This is a reasonable baseline for a JSON/AJAX
  API (SameSite=Lax cookies aren't sent on cross-site XHR/fetch, which covers the typical CSRF vector for endpoints
  that don't accept form-encoded bodies), but hasn't been pen-tested. If TRACE-X ever needs to be embeddable
  cross-site or gains a form-post-style endpoint, revisit this.

## Celery / Background Tasks

- **A `beat` process is required alongside `worker`** for `cleanup_stale_investigations` (hourly) and
  `periodic_entity_sync` (every 6h) to actually fire — both are now provisioned as separate services in both
  `docker-compose.yml` and `docker-compose.prod.yml`. If you run the worker outside these compose files (bare
  metal, a different orchestrator), remember beat is a distinct process: `celery -A src.workers.main.celery_app
  beat`.

## Infrastructure / Monitoring

- **Neo4j's Prometheus exporter is enabled but its exact metric names are unverified.** `docker-compose.prod.yml` now
  sets `NEO4J_server_metrics_prometheus_enabled=true` and a scrape job was added, but the Grafana dashboard's Neo4j
  heap-usage panel query (`neo4j_memory_heap_usage_bytes` / `neo4j_memory_heap_max_bytes`) was written without a
  live Neo4j instance to confirm those are the exact metric names Neo4j 5.x Enterprise's exporter emits — check
  `curl neo4j:2004/metrics` against a running instance and adjust the panel query if the names differ.
- **nginx/container-level metrics still aren't collected.** `nginx-exporter`/`cadvisor`/`node-exporter` were never
  deployed as services; the dashboard's "System Memory Usage" panel has no data behind it without `node-exporter`
  specifically.

## Settings Page / User Management

- **No role/status change reason or audit trail in the UI.** `PATCH /auth/users/{id}` (activate/deactivate, change
  role) exists and the Users tab's status badge is now a working toggle, but there's no confirmation dialog or
  visible history of who changed what — the change lands in the `audit_log` table (`AuditAction.USER_UPDATE`) but
  isn't surfaced anywhere in the UI.

## Docker / Deployment

- **No full image build was verified with a live Docker daemon** (none available in this sandbox) — however, static
  review of the Dockerfiles while working on the cookie-auth change above turned up three build-breaking/silently-
  broken issues that a real `docker build` would have caught immediately, all now fixed:
  - `apps/web/Dockerfile.prod` copied `.next/standalone`, which `next build` only produces when `output: 'standalone'`
    is set in `next.config.js` — it wasn't, so that `COPY` would have failed outright.
  - The same Dockerfile had `mkdir .next` / `chown nextjs:nodejs .next` as bare lines with no `RUN` prefix — invalid
    Dockerfile syntax, would have failed to parse.
  - `docker-compose.prod.yml` set `NEXT_PUBLIC_API_URL` under the frontend's `environment:` (container-start time),
    but Next.js inlines `NEXT_PUBLIC_*` vars into the client bundle at `next build` time — that setting had zero
    effect on the actual browser bundle, which would have silently baked in whatever default `lib/api.ts` falls
    back to. Fixed by passing it as a `build.args` `ARG` instead, defaulting to the relative path `/api/v1` (nginx
    already proxies that path to the backend under the same domain, so the browser never needs an absolute URL).
  - `docker-compose.prod.yml`'s `backend`/`worker` services never passed through any of the optional
    blockchain/AI/entity-intelligence env vars (`ANTHROPIC_API_KEY`, `ALCHEMY_API_KEY`, `INFURA_API_KEY`,
    `*_RPC_URL`, `CHAINALYSIS_API_KEY`, `CIPHERTRACE_API_KEY`) — an operator could fill in `docker/.env` completely
    and the containers would still never see any of it. Fixed by adding the full set to both services (see
    `docs/EXTERNAL_SERVICES_SETUP.md`).

  These were found through careful reading, not a live build — a real `docker build && up` smoke test is still the
  only way to be fully sure the images work end to end. Do that before a first real deploy, and specifically watch
  the `worker`/`beat` containers come up cleanly (their command was separately broken and fixed earlier —
  `python -m src.workers.main` doesn't start anything at all).
- **`docker/.env` is the file Compose actually reads for `docker-compose.prod.yml`**, not a root `.env.production` —
  Compose's project directory defaults to the folder of the first `-f` file, which is `docker/` for both compose
  files in this repo. `docker/.env.example` and `docs/SECRETS_MANAGEMENT.md` document this; an earlier draft of
  `docs/runbooks/deployment.md` pointed at a root `.env.production` (now corrected) and also referenced an RSA
  `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` pair that doesn't exist anywhere in the auth implementation (HS256 +
  `SECRET_KEY` only) — also corrected.
- **`docker-compose.prod.yml` env vars have no committed defaults for secrets** (`SECRET_KEY`, `POSTGRES_PASSWORD`,
  `NEO4J_PASSWORD`, `CORS_ORIGINS`, `GRAFANA_ADMIN_PASSWORD`) by design — a deploy without a populated `.env` starts
  containers with empty/invalid credentials rather than a weak-but-functional default. The compose file alone is
  not "ready to run" without an operator supplying real values first.
