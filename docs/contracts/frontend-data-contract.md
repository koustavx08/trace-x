# Frontend Data Contract

> **Status:** Baseline reference (pre-parallel-merge). Derived from `apps/web/src/lib/api.ts` (the frontend's own
> hand-written types + API client) and `packages/shared/src/index.ts` (the intended canonical shared-types package).
> **Caveat:** WS0 is expected to wire `packages/shared` into `apps/web` as a real npm workspace dependency; WS5/WS6
> touch `lib/api.ts` for auth interceptors and `getSubgraph` response shaping respectively. Re-verify which of the two
> type sources (`lib/api.ts` local interfaces vs. `@trace-x/shared` imports) is actually in use post-merge.

## Two parallel, overlapping type definitions (baseline state)

As of this baseline, `apps/web/src/lib/api.ts` defines its **own** local TypeScript interfaces (`Case`, `Wallet`,
`Transaction`, `InvestigationRun`, `Report`, `HealthResponse`, `PaginatedResponse<T>`, ...) rather than importing them
from `packages/shared/src/index.ts`, even though `packages/shared` defines a near-identical (but not identical) set.
This is exactly the gap `docs/ARCHITECTURE_GAP_ANALYSIS.md` flagged ("Missing Shared Types Package" / "Frontend
duplicates backend types"). WS0's job is to make `packages/shared` a real consumed workspace dependency — until that
lands and `lib/api.ts` is refactored to import from it, treat `lib/api.ts`'s local interfaces as the actual contract
the frontend runs on, and `packages/shared/src/index.ts` as the target/aspirational canonical version.

### Known divergences between the two (baseline)

| Field/type | `lib/api.ts` (in use) | `packages/shared/src/index.ts` (aspirational) |
|---|---|---|
| IDs | plain `string` | branded `UUID` type (`string & {__brand}`) via a `uuid()` constructor function |
| `Case.crime_type` / `status` | plain `string` | literal union types (`CrimeType`, `CaseStatus`) |
| `Wallet.entity_confidence` | plain `string \| undefined` | literal union `'CONFIRMED'\|'HIGH_CONFIDENCE'\|'PROBABLE'\|'UNKNOWN'` |
| `HealthResponse.services` | `Record<string, string>` | typed `{database, neo4j, redis: 'connected'\|'disconnected'}` |
| Chain metadata | none | `CHAINS` const map + `ChainId`/`ChainConfig` types (ethereum, polygon) |
| Report/InvestigationRun/User/APIError types | present, close match | present, close match |

## `ApiClient` (`lib/api.ts`)

Thin axios wrapper (`baseURL = NEXT_PUBLIC_API_URL`, default `http://localhost:8000/api/v1`, 30s timeout).
`get/post/patch/delete<T>()` return `response.data` directly (no envelope unwrapping needed beyond that).

**Baseline gap:** the request interceptor is a no-op (`return config` — no `Authorization` header injected), and the
response interceptor's 401 branch is an empty comment (`// Handle unauthorized`, no logic). WS5's task list targets
exactly this: inject `Authorization: Bearer <token>` from the new auth store, and implement the 401 → refresh/redirect
flow. Until WS5 lands, every authenticated backend endpoint is effectively unreachable from the frontend (no token is
ever sent).

## API surface (typed client modules in `lib/api.ts`)

| Module | Backend prefix | Notes |
|---|---|---|
| `casesApi` | `/cases` | CRUD |
| `walletsApi` | `/wallets` | CRUD |
| `investigationsApi` | `/investigations` | CRUD |
| `reportsApi` | `/reports` | CRUD (plain `Report` table) |
| `healthApi` | `/health` | check/ready/live |
| `analysisApi` | `/analysis` | validateAddress, listChains, analyzeWallet, traceFundFlow, getWalletTransactions |
| `graphApi` | `/graph` | syncWallet, getSubgraph, findPathsToVASP, checkMixer, detectPatterns, detectClusters, getWalletStats, getWalletCentrality, getTemporalFlow, lookupEntity, enrichWallet, syncEntities, health |
| `riskApi` | `/risk` | assessWallet, getAttribution, attributeWallet, generateReport, downloadReport, getCaseRiskSummary |
| `aiApi` | `/ai` | query, chat, getChatHistory, deleteChatHistory, getCapabilities, generateNarrative |

Each module's method signatures match the backend router request/response shapes documented in `api-contract.md`
almost 1:1 (the frontend types were clearly written against the backend schemas directly), with the graph module
being the one exception worth double-checking post-merge: `GraphNode`/`GraphEdge`/`SubgraphResponse` in `lib/api.ts`
are a flattened, simplified shape relative to the richer `GraphWallet`/`GraphTransaction`/`GraphEntity` dataclasses
documented in `graph-schema.md` — and per `docs/FEATURE_REALITY_MATRIX.md`, the `/graph` page was still using
placeholder/mocked data as of the last audit, so this mapping was unverified end-to-end at baseline. WS6 owns fixing
this (`getSubgraph` response shaping) — re-verify the actual `SubgraphResponse` shape once merged.

## Routes not yet backed by an auth-aware shell (baseline)

Per `docs/FEATURE_REALITY_MATRIX.md`, there is no login page, no auth store, and `<Providers>` (React Query context)
is never mounted in `app/layout.tsx` in the baseline tree — meaning `useQuery`/`useMutation` calls throw at baseline.
WS5 addresses all three. Any frontend contract testing done against the baseline tree should account for this: pages
using the `*Api` modules above via React Query will not function correctly until WS5 lands.
