# Final Test Report

> **Status: TEMPLATE — not yet filled in.** This document is scaffolding written by WS8 (Infra/CI/Docs). WS4 (backend
> test suite) and WS7 (frontend test suite) run in separate, parallel worktrees not visible to this workstream, so
> their actual pass/fail results and coverage numbers cannot be reported here yet. **Do not treat any number in this
> file as real until it has been filled in from an actual test run against the fully merged codebase.** No numbers
> have been fabricated below — every metric is a placeholder explicitly marked as such.

## How to fill this in

After WS1–WS7 are merged into the base branch:

```bash
# Backend
cd apps/api
pytest --cov=src --cov-report=term-missing --cov-report=html

# Frontend
cd apps/web
npm run build
npm test -- --coverage
```

Then replace every `<TBD>` placeholder below with the real output, and change the status line at the top from
"TEMPLATE" to the run date and commit hash it was generated against.

---

## Backend test suite (WS4 scope)

| Metric | Value |
|---|---|
| Test run date | `<TBD>` |
| Commit / branch | `<TBD>` |
| Total tests | `<TBD>` |
| Passed | `<TBD>` |
| Failed | `<TBD>` |
| Skipped | `<TBD>` |
| Line coverage (`--cov=src`) | `<TBD>%` |
| Baseline coverage (for comparison) | ~4 health-check tests only, no coverage report captured (per `docs/FEATURE_REALITY_MATRIX.md`) |

### Suite breakdown (per WS4's planned file list)

| Test file | Covers | Status |
|---|---|---|
| `test_auth.py` | login/refresh/logout/blacklist/RBAC/rate-limit/audit persistence | `<TBD>` |
| `test_ai.py` | AI query/chat with mocked `anthropic` client (never hits the real API in CI) | `<TBD>` |
| `test_reports.py` | JSON/HTML/PDF generation + mocked Celery `.delay` | `<TBD>` |
| `test_providers.py` | mocked web3/httpx, `ProviderNotConfiguredError` path | `<TBD>` |
| `test_wallets.py` | wallet CRUD/validation | `<TBD>` |
| `test_cases.py` | case CRUD | `<TBD>` |
| `test_graph.py` | graph sync/query endpoints | `<TBD>` |
| `test_risk.py` | risk assessment/attribution | `<TBD>` |

### Known risks going into this run

- `apps/api/src/api/v1/risk.py` and `apps/api/src/workers/tasks.py` import a `src.reports` module that did not exist
  in the pre-merge baseline (see `docs/contracts/report-schema.md`). If WS3 did not land before this test run, the
  app will fail to even import, and the entire suite will error at collection time rather than producing real
  pass/fail counts.
- Root `pytest.ini`'s `testpaths`/`python_files`/etc. used bracket-list syntax in the pre-WS0 baseline (invalid for a
  plain `.ini` file) — confirm WS0 landed and fixed this before assuming `pytest` collects tests correctly from the
  repo root.

## Frontend test suite (WS7 scope)

| Metric | Value |
|---|---|
| Test run date | `<TBD>` |
| Commit / branch | `<TBD>` |
| Total tests | `<TBD>` |
| Passed | `<TBD>` |
| Failed | `<TBD>` |
| Line/branch/function/statement coverage | `<TBD>` |
| Baseline coverage (for comparison) | 0 test files found (per `docs/FEATURE_REALITY_MATRIX.md`); `"test": "jest"` script existed with no `jest.config.js` backing it |

### Suite breakdown (per WS7's planned scope)

| Area | Status |
|---|---|
| Auth store (Zustand) | `<TBD>` |
| `ApiClient` interceptors (mocked axios) | `<TBD>` |
| `DashboardLayout` (regression test for the missing-export bug) | `<TBD>` |
| Graph node/edge handlers | `<TBD>` |
| Page-level smoke tests (dashboard, cases, reports, settings) | `<TBD>` |
| E2E (Playwright, optional stretch) | `<TBD>` |

## CI status (WS8 — verified by this workstream)

| Workflow | YAML syntax valid | Ran on GitHub Actions |
|---|---|---|
| `.github/workflows/backend-ci.yml` | Yes (`yaml.safe_load` check passed) | Not yet run — requires a push/PR to trigger; not executed from this sandboxed worktree |
| `.github/workflows/frontend-ci.yml` | Yes | Not yet run |
| `.github/workflows/docker-build.yml` | Yes | Not yet run |

Once this branch (or its merge into the base branch) is pushed to GitHub, confirm all three workflows actually run
and pass, and record the run URLs here.

## Docker Compose validation (WS8 — verified by this workstream)

| Check | Result |
|---|---|
| `docker/docker-compose.yml` — YAML syntax | Valid (parsed via `yaml.safe_load`; expected services present: postgres, neo4j, redis, backend, frontend) |
| `docker/docker-compose.prod.yml` — YAML syntax | Valid (parsed via `yaml.safe_load`; expected services present: nginx, frontend, backend, postgres, neo4j, redis, worker, prometheus, grafana) |
| `docker compose ... config` (full Compose-spec validation) | **Not run** — no `docker` CLI available in this sandboxed environment. Re-run both commands in a machine with Docker installed and record the actual output here before treating Docker deployment as verified. |

## Overall verdict

`<TBD — fill in once backend and frontend suites have both been run against the fully merged codebase>`
