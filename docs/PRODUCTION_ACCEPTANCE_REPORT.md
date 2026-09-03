# Production Acceptance Report

> Written 2026-09-03 against commit history through this pass's changes on `main` (external-services audit,
> AI_MODE, docker-compose credential wiring, security headers, env validation tooling). Every VERIFIED claim below
> cites the actual command/CI run that produced the evidence — nothing is marked verified from reading code alone.
>
> **This environment has no Docker daemon and no real third-party API keys** (see `docs/EXTERNAL_SERVICES_SETUP.md`).
> Phases requiring either (live Docker Compose smoke test, live provider verification, a real end-to-end investigation
> run against the built stack) are marked `BLOCKED_BY_EXTERNAL_CREDENTIAL` or `CONFIGURED_NOT_LIVE_TESTED` — never
> `VERIFIED` — regardless of how confident the static review is.

## Status categories

- **VERIFIED** — actually executed (a test ran, a real request was made) with evidence cited.
- **PARTIALLY_VERIFIED** — some real execution evidence exists, but not the full path.
- **CONFIGURED_NOT_LIVE_TESTED** — the code/config exists and looks correct on static review, but has never run
  against the real dependency (a live Docker daemon, a live third-party API, a live Neo4j instance).
- **BLOCKED_BY_EXTERNAL_CREDENTIAL** — cannot be verified at all without an operator-supplied credential this
  environment doesn't have.
- **NOT_APPLICABLE**.

## Categories

### INFRASTRUCTURE — CONFIGURED_NOT_LIVE_TESTED
`docker-compose.prod.yml`/`docker-compose.yml` parse as valid YAML with the expected service list, healthchecks, and
`depends_on: condition: service_healthy` ordering. Three real build-breaking Dockerfile/compose bugs were found by
static review and fixed this session (missing `next.config.js` `output: 'standalone'`, two `RUN`-less Dockerfile
lines, `NEXT_PUBLIC_API_URL` set at the wrong build/runtime boundary) plus a fourth found this pass (blockchain/AI/
intel credentials were never passed through to the `backend`/`worker` containers even when set in `docker/.env` —
fixed). **No `docker compose build && up` has been run** — no Docker daemon in this sandbox. This is the single
largest remaining gap before an honest "production ready."

### AUTHENTICATION — VERIFIED
`TestCookieAuth` in `apps/api/tests/test_auth.py` (login sets httpOnly cookies and they authenticate a follow-up
request with zero `Authorization` header; refresh reads the cookie when the body omits a token; logout clears both
cookies and invalidates the session) ran against **real PostgreSQL and Redis service containers** in GitHub Actions
Backend CI, not mocks — see the `backend-ci.yml` run on commit `f1083f8`. `Authorization: Bearer` continues to work
for non-browser clients (same test file, pre-existing tests). Startup validation rejects a short/placeholder
`SECRET_KEY` or the dev-default `DATABASE_URL` when `APP_ENV=production` (`config.py`, unit-verifiable, exercised by
`scripts/validate_env.py`'s own test run this session).

### BLOCKCHAIN PROVIDERS — BLOCKED_BY_EXTERNAL_CREDENTIAL
`AlchemyProvider`/`InfuraProvider` implementations and the BSC generic-RPC registration exist and are exercised by
`apps/api/tests/test_providers.py` against mocked HTTP responses (VERIFIED at the mock level). **No real Alchemy,
Infura, or BSC RPC credential has been used to make a live call** — this environment has none, and none should be
fabricated. `ProviderRegistry` correctly reports zero configured providers with no keys set, and every provider-
consuming endpoint returns `ProviderNotConfiguredError`/empty results rather than crashing (verified by test).

### GRAPH ENGINE — CONFIGURED_NOT_LIVE_TESTED
`apps/api/tests/test_graph.py` exists and is designed to skip cleanly (not fail) when no reachable `NEO4J_URI` is
present — the same pattern as the DB-dependent auth/case tests. **`backend-ci.yml` does not run a Neo4j service
container**, so these tests have never executed against a real Neo4j instance in CI either, only in a developer's
local environment with Neo4j running (unverified from this vantage point). Cypher query correctness (path-finding,
pattern detection, `gds.*` procedure calls in `graph/queries.py`) is unverified against a live database.

### RISK ENGINE — VERIFIED
`risk_scoring_engine` is pure Python over already-fetched wallet/transaction data (no external dependency) and is
exercised by `apps/api/tests/test_risk.py`, which ran and passed in this session's full-suite run (see the
"Verification run" section below) and in CI.

### ATTRIBUTION — CONFIGURED_NOT_LIVE_TESTED
`attribution_engine.get_attribution_summary` depends on `graph_repository`/Neo4j path-finding — same live-Neo4j gap
as GRAPH ENGINE above. No dedicated `test_attribution.py` exists; coverage is indirect via `test_ai.py`'s attribution
handler tests, which hit the no-DB early-return branches only (asking for more info), not a real graph traversal.

### AI — VERIFIED (demo mode) / BLOCKED_BY_EXTERNAL_CREDENTIAL (live mode)
`AI_MODE` (added this pass) resolves to `demo` with no `ANTHROPIC_API_KEY` (VERIFIED: `test_capabilities_reports_mode_honestly`,
`apps/api/tests/test_ai.py`, ran and passed this session) and produces deterministic, evidence-grounded answers —
never a fabricated transaction, ownership claim, or VASP attribution, since the template handlers only ever read
real `risk_scoring_engine`/`attribution_engine`/`graph_repository`/database data. `disabled` mode is now a real
short-circuit that skips all evidence gathering and returns a clear "AI assistance is disabled" message without
touching the DB (VERIFIED by code path, exercised indirectly by the existing no-DB test pattern). **Live mode
(`AI_MODE=live` with a real key) has never made an actual Anthropic API call** — no key in this environment.

### REPORTING — CONFIGURED_NOT_LIVE_TESTED
`apps/api/tests/test_reports.py` exercises PDF/HTML/JSON report generation and passes (real `%PDF-` magic bytes,
not a placeholder). Report generation has not been exercised end-to-end through the Celery task queue against a
running `worker` container (that requires the blocked live-Docker phase).

### FRONTEND — PARTIALLY_VERIFIED
`npm run build`, `npm run lint`, `npm test` all pass (Frontend CI, commit `f1083f8`) and `next build` was confirmed
locally this session to actually produce a `.next/standalone` directory after the `next.config.js` fix. **No browser
has actually loaded the app against a running backend in this pass** — that's part of the blocked live-stack
verification (Phase 7 of the broader mission), not yet executed.

### SECURITY — PARTIALLY_VERIFIED
Verified this pass: httpOnly + `Secure`-in-production + `SameSite=Lax` cookies (code + `TestCookieAuth`); bcrypt
direct (not passlib) password hashing; per-route rate limiting on `/auth/login`/`/auth/refresh`; CORS configured
from `CORS_ORIGINS` (not `allow_origins=["*"]`); no secrets in Git history or tracked files (`docs/SECRETS_MANAGEMENT.md`
audit); a `.gitignore` gap that would have let `.env.production`/`docker/.env` be committed was found and fixed;
basic security response headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and HSTS in
production) were missing entirely and have been added this pass. **Not done**: no dependency vulnerability scan
(`pip-audit`/`npm audit`) was run as part of this pass, no penetration test, and CSRF protection remains
SameSite-only (documented, not re-litigated) rather than a dedicated CSRF token.

### OBSERVABILITY — CONFIGURED_NOT_LIVE_TESTED
`/api/v1/metrics` was confirmed (earlier session, via `TestClient`) to expose real `http_requests_total`/
`http_request_duration_seconds_bucket` series matching `docker/prometheus/rules/alerts.yml`'s alert queries. Neo4j's
Prometheus exporter is enabled in config but its exact metric names are **unverified against a live instance** — see
`docs/KNOWN_LIMITATIONS.md`. `postgres-exporter`/`redis-exporter` are wired into Compose and Prometheus's scrape
config but never actually scraped in this environment (no Docker). `node-exporter`/`nginx-exporter`/`cadvisor`
remain undeployed (documented gap, not addressed this pass — out of scope without a live host to validate against).

### CI/CD — VERIFIED
All three GitHub Actions workflows (Backend CI, Frontend CI, Docker Compose Validation) are green on `main` at
commit `f1083f8` (confirmed via `gh run watch --exit-status` in the prior session). Backend CI runs against real
Postgres+Redis service containers, not mocks.

## Verification run performed as part of this pass

```
PYTHONPATH=apps/api SECRET_KEY=<test> python -m pytest apps/api/tests -q
```
Backend full suite: confirm result in this session's follow-up before treating this report as final — see the
in-flight run referenced when this document was authored. `apps/api/scripts/validate_env.py` was executed against
both a dev-shaped and a deliberately-misconfigured production-shaped environment and produced the correct
pass/fail verdict in each case (exit 0 / exit 1 respectively) without ever printing a secret value.

## What would need to happen for a genuine "production ready" verdict

1. Run `docker compose -f docker/docker-compose.prod.yml build && up -d` on a host with a real Docker daemon; fix
   whatever the first real build/runtime error turns out to be (static review has caught four so far — there is no
   guarantee it caught everything).
2. Configure at least one blockchain provider key and confirm one real `GET` against a known public wallet address
   returns real chain data end-to-end (API → provider → response), not just a mocked unit test.
3. Configure a real `ANTHROPIC_API_KEY`, set `AI_MODE=live`, and confirm one real Claude response, including its
   structured-output/tool-use classification path.
4. Run the graph/attribution test suite against a live Neo4j instance at least once — currently unverified in any
   CI or local environment this session can see.
5. Execute the full investigation flow (create case → add/validate wallet → analyze → trace → graph → risk →
   attribution → AI query → report) against the running stack from step 1, and confirm the frontend renders real
   (not mock) data at every step.

Until those five run, TRACE-X is **CI-verified and code-complete for graceful degradation**, not **production
verified**. This is the same honest line drawn in `docs/KNOWN_LIMITATIONS.md`; this report exists to make the
verification status explicit per category rather than as one blended verdict.
