# TRACE-X Production Readiness

> **Status:** Written as part of WS8 (Infra/CI/Docs). Consolidates `docs/FEATURE_REALITY_MATRIX.md` and
> `docs/ARCHITECTURE_GAP_ANALYSIS.md` (both dated 2024-08-27, commit `fdeb525`) with the intended end-state from the
> 9-workstream production-readiness plan (WS0–WS8), and this workstream's own verified changes.
> **This document reflects the pre-parallel-merge baseline plus WS8's own infra/docs work.** WS1–WS7 land in parallel
> worktrees not visible to this workstream — re-verify every "Planned (WSn)" row below against actual merged code,
> and update the status column accordingly, once all workstreams are merged.

## How to read this document

- **Done** — verified working in the current merged tree.
- **Done (WS8)** — implemented by this workstream, verified per the "Verification" sections below.
- **Planned (WSn)** — targeted by a specific workstream per the execution plan; not yet verified from this vantage point.
- **Gap** — known issue, no owner confirmed to have fixed it yet.

## Summary status matrix

| Area | Baseline status | Target workstream | End-state expectation |
|---|---|---|---|
| npm workspaces / shared types wiring | Not implemented | WS0 | `packages/shared` consumed by `apps/web`; root `package.json` workspaces |
| Root `pytest.ini` syntax | Broken (bracket-list values) | WS0 | Fixed to space-separated values; `pytest --collect-only` succeeds from repo root |
| Dead test-runner scripts | Present (`run_tests*.py`, `fix_imports.py`) | WS0 | Removed |
| Auth: login/refresh | Backend implemented, unverified | Existing | `/auth/login`, `/auth/refresh` exist |
| Auth: logout + token blacklist | Not implemented | WS1 | JTI claim + Redis blacklist, `AuditAction.LOGOUT` wired |
| Auth: `SECRET_KEY` validation | Insecure runtime default (`secrets.token_urlsafe(32)`) | WS1 | Required from env in production, validated at startup |
| Rate limiting | Not implemented | WS1 | `/auth/login`, `/auth/refresh` rate-limited (e.g. 5/min/IP) |
| Audit logging | In-memory buffer, no-op flush | WS1 | Persistent `AuditLog` table + real async DB writes |
| AI assistant | Template/regex dispatch, no LLM | WS2 | Real Claude calls with graceful template fallback when `ANTHROPIC_API_KEY` unset |
| AI chat session storage | In-memory class dict (baseline) | WS2 | Redis-backed |
| Report generation (`src/reports`) | **Missing module — broken import in baseline** | WS3 | Real module with PDF/HTML/JSON rendering |
| Report PDF output | Hardcoded placeholder bytes, not real PDF | WS3 | Real PDF (`%PDF-` magic bytes) |
| Blockchain providers: Alchemy | Implemented (needs API key) | Existing | Working with a real key |
| Blockchain providers: Infura | Partially stubbed (`get_transactions_by_address`/`get_token_transfers` return `[]`) | WS3 | Fully implemented |
| Blockchain providers: Chainalysis/CipherTrace | Not implemented | WS3 | New provider modules, `ProviderNotConfiguredError` when key absent |
| Celery task wiring (analysis/report endpoints) | Endpoints call services inline (blocking) | WS3 | Endpoints dispatch `.delay()`, return task id |
| Backend test coverage | ~4 health-check tests only | WS4 | Materially increased coverage across auth/ai/reports/providers/wallets/cases/graph/risk |
| Frontend auth UI | Not implemented — no login page | WS5 | Login page, auth store, middleware-gated routes |
| `<Providers>` (React Query) mounted | Not mounted — `useQuery`/`useMutation` throw | WS5 | Mounted in `app/layout.tsx` |
| `lib/api.ts` 401 interceptor / auth header | Stubbed (no-op) | WS5 | Real interceptor + Bearer header injection |
| Graph visualization | Mocked/placeholder | WS6 | Real ReactFlow rendering from `graphApi.getSubgraph`, real layout, draggable nodes |
| Reports page | Uses `mockReports` | WS6 | Wired to real reports API |
| Settings page (user management) | Uses `mockUsers`; no backend user-mgmt endpoint confirmed | WS6 | Wired if a backend endpoint exists, else gap documented (see `KNOWN_LIMITATIONS.md`) |
| Frontend test coverage | 0 test files (Jest configured, unbacked) | WS7 | `jest.config.js`/`jest.setup.js` + component/page tests |
| CI/CD | None | **WS8 (this workstream) — done** | `backend-ci.yml`, `frontend-ci.yml`, `docker-build.yml`, `dependabot.yml` |
| Docker prod compose secrets | Hardcoded weak passwords, placeholder CORS origin | **WS8 — done** | `${VAR}` env substitution, no committed secret defaults |
| Docker prod compose postgres init mount | Referenced a non-existent `./postgres/init` directory | **WS8 — done** | Mount removed (Alembic owns schema; no extension bootstrap needed) |
| Prometheus scrape config | Referenced undeployed exporters (postgres/redis/nginx-exporter, cadvisor, node-exporter) | **WS8 — done** | Trimmed to actually-deployed targets (prometheus, tracex-backend, tracex-frontend); rest tracked in `KNOWN_LIMITATIONS.md` |
| Prometheus alert rules | `rule_files: "rules/*.yml"` pointed at a non-existent directory | **WS8 — done** | `docker/prometheus/rules/alerts.yml` added (service-down, high error rate, high latency) |
| Contract documentation (`docs/contracts/*.md`) | Missing (10 files) | **WS8 — done** | All 10 written against baseline code, caveated for post-merge refresh |

## What WS8 verified directly

- `.github/workflows/backend-ci.yml`, `frontend-ci.yml`, `docker-build.yml`, `.github/dependabot.yml` — all parse as
  valid YAML (`yaml.safe_load`).
- `docker/docker-compose.yml` and `docker/docker-compose.prod.yml` both parse as valid YAML with the expected service
  lists (`docker compose config` itself could not be run in this environment — no `docker` CLI available in the
  sandbox — see `docs/FINAL_TEST_REPORT.md` for a note on re-running this check with Docker installed).
- `docker/prometheus/prometheus.yml` and `docker/prometheus/rules/alerts.yml` parse as valid YAML.
- Confirmed via `apps/api/alembic/versions/*.py` that all primary keys use Python-side `uuid.uuid4()` defaults (not
  Postgres-side `gen_random_uuid()`), so removing the `./postgres/init` mount does not lose any needed
  extension/bootstrap behavior — Alembic alone owns schema creation.

## Overall verdict (unchanged from prior audit, pending WS1–WS7 merge)

The prior audit's verdict — **"demo-ready with caveats, not production-ready"** — still stands as the honest baseline
assessment. This workstream closes the CI/CD, Docker hardening, monitoring, and documentation gaps identified in that
audit. The remaining gaps (auth UI, real AI/PDF/provider integrations, test coverage) are owned by WS1–WS7 and were
not visible to this workstream's worktree. Once all workstreams merge, re-run the end-to-end verification checklist
in the project plan (`pytest --cov`, `npm run build && npm test`, Docker compose validation with the CLI actually
available, and a manual smoke test of login → dashboard → graph → reports → AI) before calling the system
production-ready.
