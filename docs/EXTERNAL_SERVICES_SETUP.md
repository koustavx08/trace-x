# External Services Setup

> Audited directly against the current codebase (`apps/api/src/core/config.py`, `apps/api/src/providers/*`,
> `apps/api/src/ai/service.py`, `docker/docker-compose.prod.yml`) on 2026-09-03. Every credential below is a real
> `Settings` field that something in the code actually reads — nothing here is aspirational.

No credential in this document should ever be typed into source code, a commit, or a chat/PR. Set it in a local,
git-ignored `.env` (see `.env.example` / `docker/.env.example`) or your deployment platform's secret manager. See
`docs/SECRETS_MANAGEMENT.md` for the full policy.

## Audit table

| Provider | Purpose | Required? | Env Variable(s) | Side | Required Permissions / Scope | Free Tier | Production Criticality | Fallback Behavior |
|---|---|---|---|---|---|---|---|---|
| PostgreSQL | Primary relational store (cases, wallets, users, audit log, reports) | **Required** | `DATABASE_URL` | Server-side only | Own database, `CREATE`/`ALTER` for Alembic migrations | Yes (any Postgres 15 host, incl. free tiers on Neon/Supabase/Railway) | REQUIRED_FOR_CORE | None — app fails startup DB checks / 500s on every DB-backed route without it. |
| Redis | Celery broker/result backend, AI chat session store, JTI token-revocation blacklist | **Required** | `REDIS_URL` | Server-side only | None beyond network access | Yes (Redis Cloud, Upstash free tiers) | REQUIRED_FOR_CORE | None for chat/blacklist paths — see `docs/KNOWN_LIMITATIONS.md`. Celery tasks simply never run without it. |
| Neo4j | Graph engine (wallet/transaction graph, path-finding, pattern detection) | **Required** | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Server-side only | Read/write on the graph DB; `apoc`/`gds` plugins for full pattern-detection queries | Yes (Neo4j AuraDB Free) | REQUIRED_FOR_CORE | None — graph/pattern/attribution endpoints depend on it directly. |
| JWT session secret | Signs/verifies access & refresh tokens (HS256) | **Required** | `SECRET_KEY` | Server-side only | N/A — a random secret, not a third-party account | N/A | REQUIRED_FOR_CORE | App refuses to start in production with a short/placeholder value (`config.py`'s startup validator). |
| Anthropic (Claude) | AI Investigation Assistant — natural-language Q&A, narrative report generation | Optional | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `AI_MODE` | Server-side only (never sent to the browser) | Standard API key, no special scope | Yes (Anthropic Console gives free trial credits) | OPTIONAL_ENHANCEMENT | `AI_MODE` auto-selects `demo`: deterministic, evidence-grounded template answers over the same real data, never fabricated. See Phase 4 / `src/ai/service.py`. |
 | OpenRouter | AI Investigation Assistant — natural-language Q&A, narrative report generation (via OpenRouter) | Optional | `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`, `AI_MODE`, `AI_PROVIDER` | Server-side only (never sent to the browser) | Standard API key, no special scope | Yes (OpenRouter offers free trial credits) | OPTIONAL_ENHANCEMENT | When `AI_MODE=live` and `AI_PROVIDER=openrouter`, uses the OpenRouter API. Falls back to demo mode if not configured. |
| Alchemy | Ethereum/Polygon/Arbitrum/Optimism/Base chain data (balances, transactions, token transfers) | Optional | `ALCHEMY_API_KEY` | Server-side only | "Read" API key from an Alchemy app per network | Yes (Alchemy free tier, 300M compute units/mo) | REQUIRED_FOR_CORE *for real chain data* / OPTIONAL_ENHANCEMENT otherwise | `ProviderRegistry` simply has no provider for that chain; endpoints return `ProviderNotConfiguredError` / empty results, never crash. |
| Infura | Same as Alchemy — used as the alternate/fallback EVM RPC vendor, and its plain-JSON-RPC client is reused for BSC | Optional | `INFURA_API_KEY`, `INFURA_API_SECRET` | Server-side only | Standard Infura project ID/secret | Yes (Infura free tier) | OPTIONAL_ENHANCEMENT | Same as Alchemy. |
| BSC RPC endpoint | BNB Smart Chain data (no Alchemy/Infura vendor support) | Optional | `BSC_RPC_URL` | Server-side only | Any JSON-RPC endpoint — public node or a vendor (Ankr/QuickNode/Chainstack) | Yes (public BSC RPC nodes are free) | OPTIONAL_ENHANCEMENT | No BSC provider registered; BSC wallets/analysis unavailable, no crash. |
| Chainalysis | Commercial entity/sanctions intelligence (KYT address screening) | Optional | `CHAINALYSIS_API_KEY` | Server-side only | Licensed Chainalysis KYT API access (commercial contract, not self-serve) | No (enterprise/licensed only) | OPTIONAL_ENHANCEMENT | `ChainalysisProvider.__init__` raises `ProviderNotConfiguredError`; entity-intelligence lookups degrade to internal graph data only — never fabricated attribution. |
| CipherTrace | Commercial entity/sanctions intelligence (Mastercard) | Optional | `CIPHERTRACE_API_KEY` | Server-side only | Licensed CipherTrace API access (commercial contract) | No (enterprise/licensed only) | OPTIONAL_ENHANCEMENT | Same as Chainalysis. |
| OFAC SDN list | Sanctions-list reference data (public, not an API key) | Optional | `OFAC_SDN_LIST_URL` | Server-side only | None — public CSV | Yes (always free, U.S. Treasury) | OPTIONAL_ENHANCEMENT | Defaults to the real Treasury URL already; only relevant if you need to point at a mirror. |
| Grafana admin | Dashboard login for the monitoring stack | Required *if deploying monitoring* | `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` | Server-side only (self-hosted container) | N/A — a local admin password, not a third-party account | N/A (self-hosted, `docker-compose.prod.yml`) | PRODUCTION_MONITORING | Compose substitutes an empty string with a warning if unset; Grafana then has no usable admin login until set. |
| Prometheus/Grafana scrape targets | Metrics collection (API, Postgres, Redis, Neo4j) | Required *if deploying monitoring* | none (internal Docker service names) | Server-side only | N/A | Yes (self-hosted, no SaaS cost) | PRODUCTION_MONITORING | `docker/prometheus/prometheus.yml` scrapes fail silently for a target that isn't running; dashboards show gaps, app is unaffected. |
| Email / report delivery | — | N/A | — | — | — | — | NOT_APPLICABLE | **Not implemented in this codebase.** No SMTP/SendGrid/Mailgun client exists anywhere in `apps/api/src`; reports are generated as PDF/HTML/JSON and downloaded via the API, not emailed. Don't configure credentials for this — there's nothing to consume them. |
| Cloud deployment provider (AWS/GCP/Azure/Vercel/etc.) | — | N/A | — | — | — | — | NOT_APPLICABLE | The codebase has no provider-specific SDK calls (no `boto3`, no GCP/Azure client libraries). Deployment is Docker Compose-based; see `docs/DEPLOYMENT_ARCHITECTURE.md` for a recommended managed-infra mapping that needs no code changes. |

## Classification legend

- **REQUIRED_FOR_CORE** — the application cannot serve its primary function without this.
- **OPTIONAL_ENHANCEMENT** — the platform runs and demos correctly without it; this unlocks real (non-synthetic) data
  or a specific capability.
- **DEMO_ONLY** — not currently applicable; no provider in this table exists solely for demo purposes (the AI
  assistant's demo mode is a *fallback behavior* of a real provider, not a separate demo-only integration).
- **PRODUCTION_MONITORING** — needed for operating a production deployment, not for the investigation features
  themselves.

## How to obtain each optional credential

1. **Anthropic (`ANTHROPIC_API_KEY`)** — console.anthropic.com → **Settings → API Keys** → Create Key. No special
   scope; a standard key is sufficient. Free trial credits are available for new accounts; production use is
   pay-as-you-go.
2. **Alchemy (`ALCHEMY_API_KEY`)** — dashboard.alchemy.com → **Create App** per network you need (Ethereum, Polygon,
   Arbitrum, Optimism, Base) → copy the API key from the app's "View Key" panel. The free tier is sufficient to
   validate the integration; production volume may need a paid plan.
3. **Infura (`INFURA_API_KEY` / `INFURA_API_SECRET`)** — infura.io → **Create New API Key** → enable the networks you
   need under "Endpoints". The project ID is the API key; the secret is only needed if you use Infura's authenticated
   endpoints.
4. **BSC RPC (`BSC_RPC_URL`)** — either a public endpoint (e.g. `https://bsc-dataseed.binance.org`) for light use, or
   a vendor (Ankr, QuickNode, Chainstack) dashboard for a dedicated/rate-limited endpoint.
5. **Chainalysis / CipherTrace** — these are enterprise sales-led products, not self-serve signup. Contact the
   vendor's sales team for a KYT/attribution API license; there is no free tier. Do not attempt to substitute a
   scraped or unofficial source — leave the feature disabled/degraded instead (see `docs/KNOWN_LIMITATIONS.md`).

1. **OpenRouter (`OPENROUTER_API_KEY`)** — openrouter.ai → **Keys** → Create Key. Standard API key is sufficient. Free trial credits are available for new accounts; production use is pay-as-you-go.


After setting any of these, run `cd apps/api && python scripts/validate_env.py` to confirm they're picked up
correctly before deploying (see `docs/SECRETS_MANAGEMENT.md`).
