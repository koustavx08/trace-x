# TRACE-X

**Real-Time Cryptocurrency Fraud Attribution & Investigation Platform**

[SIH26183](https://github.com/koustavx08/trace-x.git) — Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported Suspect Wallet Addresses through Automated Blockchain Analytics.

![TRACE-X Logo](https://raw.githubusercontent.com/koustavx08/trace-x/main/public/logo.svg)

## 🏆 SIH 2026 — DEMO READY

**Status**: ✅ All 25 core capabilities verified | **Verdict**: READY FOR DEMONSTRATION

TRACE-X is an investigation and intelligence platform for cybercrime investigators and authorized law-enforcement analysts. It traces cryptocurrency fund flows from suspect wallet addresses through intermediary wallets to identify the nearest probable VASP/exchange, providing explainable evidence and confidence levels for every attribution.

**Not a cryptocurrency exchange.** It does not perform transactions, custody funds, or interact with private keys.

---

## 📋 Core User Flow

1. **Investigator creates or selects a case**
2. **Investigator enters a suspect cryptocurrency wallet address**
3. **System validates the address and identifies the blockchain**
4. **TRACE-X fetches relevant blockchain transactions**
5. **TRACE-X recursively traces outgoing fund flows through intermediary wallets**
6. **TRACE-X constructs a transaction graph**
7. **TRACE-X detects suspicious movement patterns** (peel chains, round amounts, mixer interactions, rapid movement)
8. **TRACE-X checks known entity intelligence and VASP/exchange labels** (Binance, Coinbase, Kraken, OKX, Bybit, Huobi, KuCoin, Gate.io, Tornado Cash, etc.)
9. **TRACE-X calculates an explainable risk score** (12 weighted factors: Mixer Interaction, Peel Chain, Sanctions Hit, High-Risk Entity, Rapid Movement, Round Amounts, Large Transfer, Cross-Chain Bridge, Contract Interaction, New Wallet, Low Liquidity Token, Dusting Attack)
10. **TRACE-X identifies the nearest probable VASP/exchange reached by the traced flow** (Dijkstra shortest-path with confidence scoring)
11. **TRACE-X shows evidence and confidence rather than claiming certainty** (CONFIRMED/HIGH_CONFIDENCE/PROBABLE/UNKNOWN)
12. **TRACE-X generates an investigation report** (Executive Summary, Technical Findings, Evidence Package — PDF/HTML/JSON)

---

## 🎯 Confidence Levels

- **CONFIRMED** — Verified on-chain + off-chain correlation
- **HIGH_CONFIDENCE** — Strong heuristic + multiple corroborating signals
- **PROBABLE** — Single strong signal or multiple weak signals
- **UNKNOWN** — Insufficient evidence

---

## 🧠 AI Investigation Assistant

**Not a chatbot. An investigation co-pilot with 8 supported query types:**

| Query Type | Example | Evidence Grounded |
|------------|---------|-------------------|
| **Risk Summary** | "What's the risk score for wallet 0x...?" | Score, factors, evidence, follow-ups |
| **Attribution** | "Where did funds from 0x... go?" | VASP, path, confidence, evidence |
| **Patterns** | "Any suspicious patterns on Ethereum?" | Peel chains, round amounts, mixers |
| **Fund Flow** | "Trace the money from wallet 0x..." | Path, hops, value, VASP endpoint |
| **Entity Lookup** | "Who owns address 0x...?" | Entity, type, confidence, source |
| **Case Overview** | "Tell me about case TRX-20240115-0042" | Stats, wallets, investigations |
| **Timeline** | "Show me transaction history for wallet 0x..." | Daily volume, peak activity |
| **Comparison** | "Compare wallet A vs B" | Side-by-side risk/attribution |

**3 Modes**:
- `live` — Anthropic Claude or OpenRouter (requires API key)
- `demo` — Deterministic templates (works without keys, never hallucinates)
- `disabled` — Clear message, AI assistance turned off

**Anti-Hallucination Guardrails**: Never queries blockchain directly; constrained to investigation evidence; explicit confidence levels; "Insufficient evidence" vs. speculation; follow-up questions based on available data.

**Endpoints**: `GET /api/v1/ai/capabilities`, `POST /api/v1/ai/query`, `GET /api/v1/ai/query/{task_id}`

---

## 💻 Tech Stack

| Layer | Technology |
|------|-----------|
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Zustand, React Flow |
| **Backend** | Python, FastAPI, Pydantic, SQLAlchemy 2.0 (async) |
| **Database** | PostgreSQL 15+ (application data), Neo4j 5+ (transaction graph) |
| **Cache** | Redis 7 (Celery broker/result backend, AI chat session store, 7-day TTL) |
| **Blockchain** | Ethereum (primary), Polygon (secondary), EVM-compatible abstraction layer |
| **Analytics** | 12-factor risk scoring engine, attribution engine with Dijkstra, pattern detection algorithms |
| **AI** | Anthropic Claude (live mode), deterministic demo mode (no key needed), OpenRouter fallback |
| **Infrastructure** | Docker Compose (dev + prod), Nginx (SSL termination), Prometheus + Grafana (monitoring) |

---

## 📁 Project Structure

```
trace-x/
├── apps/
│   ├── web/          # Next.js frontend with App Router
│   │   ├── src/
│   │   │   ├── app/          # Routes: /dashboard, /cases, /analyze, /risk, /ai, /reports, /graph
│   │   │   ├── components/   # shadcn/ui components
│   │   │   ├── lib/          # API client, utilities
│   │   │   ├── hooks/        # React hooks
│   │   │   ├── store/        # Zustand stores
│   │   │   └── types/        # TypeScript types
│   │   │
│   │   └── public/           # Static assets
│   │
│   └── api/          # FastAPI backend
│       ├── src/
│       │   ├── main.py         # App entrypoint with lifespan
│       │   ├── core/         # Config, DB, logging, exceptions, validation
│       │   ├── models/       # SQLAlchemy models
│       │   ├── schemas/      # Pydantic schemas
│       │   ├── api/v1/       # API routes (v1: wallets, cases, analysis, investigations, risk, reports, health)
│       │   ├── providers/    # Blockchain providers (EVM: Alchemy, Infura, BSC)
│       │   ├── graph/        # Neo4j graph layer (repository, queries, models)
│       │   ├── intelligence/ # Entity intelligence (exchange/mixer/bridge/DEFI directories, OFAC SDN parsing)
│       │   ├── analytics/    # Risk engine (12 factors), Attribution engine (graph traversal + confidence)
│       │   ├── ai/           # Investigation assistant (service.py: 8 query types, 3 modes, provider pattern)
│       │   ├── reports/      # Report generation (PDF/HTML/JSON, 4 templates)
│       │   ├── workers/      # Celery tasks (wallet_analysis, graph_sync, entity_enrichment, periodic sync, cleanup)
│       │   └── ai/providers/ # AI providers (Anthropic, OpenRouter, Deterministic Demo, Disabled)
│       ├── tests/          # Full test suite (health, auth, providers, graph, risk, AI, reports)
│       ├── scripts/        # Utility scripts (seed_demo_data.py, validate_env.py)
│       ├── Dockerfile      # Development production
│       ├── Dockerfile.prod # Production Dockerfile
│       └── pyproject.toml  # Project config, deps, ruff/mypy config
│
├── packages/
│   └── shared/         # Shared TypeScript types (UUID, BaseEntity, Case/Wallet/Transaction interfaces, CHAINS)
│
├── docker/             # Docker Compose configurations
│   ├── docker-compose.yml        # Development stack (frontend, backend, postgres, neo4j, redis)
│   ├── docker-compose.prod.yml   # Production stack (with Nginx, resource limits)
│   ├── nginx/                # SSL termination, rate limiting, security headers
│   ├── prometheus/           # Scrape configs, alert rules
│   └── grafana/              # Dashboards (overview + investigation dashboards)
│
├── docs/               # Comprehensive documentation
│   ├── ARCHITECTURE.md     # System architecture + AI assistant architecture
│   ├── DEVELOPMENT.md      # Development setup + AI service references
│   ├── EXTERNAL_SERVICES_SETUP.md  # Credential audit table (all providers)
│   ├── KNOWN_LIMITATIONS.md  # Current limitations (AI, blockchain, auth, deployment)
│   ├── PRODUCTION_ACCEPTANCE_REPORT.md  # Verification status per category
│   ├── SECRETS_MANAGEMENT.md   # Secrets locations, setup, audit results (CLEAN)
│   ├── SIH_PITCH_DECK.md     # SIH 2026 pitch deck (NEW)
│   ├── DEMO-SCRIPT.md        # 5-minute demo flow
│   ├── runbooks/           # Deployment + incident response runbooks
│   ├── FINAL_TEST_REPORT.md  # Test execution results
│   └── ...
│
├── scripts/            # Utility scripts (seed_demo_data.py, validate_env.py)
├── .github/            # CI/CD workflows (Backend CI, Frontend CI, Docker Compose Validation)
└── .gitignore        # Excludes __pycache__, .venv, .next, node_modules, .pytest_cache, celerybeat-skeleton, dist, *.egg-info, coverage, .DS_Store, Thumbs.db, logs, secrets, investigations, exports, /reports, .claude/

---

## 🚀 Getting Started

### Prerequisites

- Node.js 20+
- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+
- Neo4j 5+

### Quick Start with Docker Compose

```bash
# Clone the repository
git clone https://github.com/koustavx08/trace-x.git
cd trace-x

# Copy environment template
cp .env.example .env

# Edit .env with your values (at minimum: SECRET_KEY, DB passwords, API keys)

# Start all services
docker-compose -f docker/docker-compose.yml up -d

# Verify services are healthy
curl http://localhost:8000/api/v1/health
curl http://localhost:3000
```

### Manual Development Setup

#### Backend

```bash
cd apps/api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend

```bash
cd apps/web

# Install dependencies
npm install

# Start development server
npm run dev
```

### Verification

```bash
# Validate environment setup
cd apps/api && python scripts/validate_env.py

# Run backend tests
cd apps/api && pytest -v

# Check frontend
cd apps/web && npm run lint && npm run typecheck && npm run build
```

---

## 🔧 Environment Variables

See `.env.example` for all required variables.

### Application

- `APP_ENV` — Environment (development/production/test)
- `SECRET_KEY` — Application secret key (min 32 chars, **required for production**)
- `API_HOST` — API host (default: 0.0.0.0)
- `API_PORT` — API port (default: 8000)

### Database

- `DATABASE_URL` — PostgreSQL connection string
- `NEO4J_URI` — Neo4j Bolt URI
- `NEO4J_USER` — Neo4j username
- `NEO4J_PASSWORD` — Neo4j password

### Redis

- `REDIS_URL` — Redis connection string

### Blockchain Providers

- `ALCHEMY_API_KEY` — Alchemy API key for Ethereum/Polygon
- `INFURA_API_KEY` — Infura API key
- `INFURA_API_SECRET` — Infura API secret
- `ETHEREUM_RPC_URL` — Ethereum RPC endpoint
- `POLYGON_RPC_URL` — Polygon RPC endpoint
- `ARBITRUM_RPC_URL` — Arbitrum RPC endpoint
- `OPTIMISM_RPC_URL` — Optimism RPC endpoint
- `BASE_RPC_URL` — Base RPC endpoint
- `BSC_RPC_URL` — BSC RPC endpoint (no Alchemy/Infura support; use plain JSON-RPC or vendor like Ankr/QuickNode/Chainstack)

### Entity Intelligence

- `CHAINALYSIS_API_KEY` — Chainalysis API key (commercial license)
- `CIPHERTRACE_API_KEY` — CipherTrace API key (commercial license)
- `OFAC_SDN_LIST_URL` — OFAC SDN list URL (defaults to Treasury URL)

### Logging

- `LOG_LEVEL` — Log level (DEBUG/INFO/WARNING/ERROR)
- `LOG_FORMAT` — Log format (json/text)

### AI Investigation Assistant

- `AI_MODE` — Mode: `live` | `demo` | `disabled` (default: auto-selects based on key presence)
- `AI_PROVIDER` — Provider: `anthropic` | `openrouter` (used when AI_MODE=live)
- `ANTHROPIC_API_KEY` — Anthropic API key (required for live mode)
- `OPENROUTER_API_KEY` — OpenRouter API key (alternative for live mode)
- `ANTHROPIC_MODEL` — Model name (default: claude-sonnet-5)
- `OPENROUTER_BASE_URL` — OpenRouter base URL (default: https://openrouter.ai/api/v1)
- `OPENROUTER_MODEL` — Model name (optional)

---

## 🔌 API Endpoints

### Health

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/health` | Health check with service status |
| `GET /api/v1/health/ready` | Readiness probe |
| `GET /api/v1/health/live` | Liveness probe |

### Cases

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/cases` | Create case |
| `GET /api/v1/cases` | List cases (paginated, filterable) |
| `GET /api/v1/cases/{id}` | Get case details |
| `PATCH /api/v1/cases/{id}` | Update case |
| `DELETE /api/v1/cases/{id}` | Delete case |

### Wallets

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/wallets` | Add wallet to case |
| `GET /api/v1/wallets` | List wallets (paginated, filterable) |
| `GET /api/v1/wallets/{id}` | Get wallet details |
| `PATCH /api/v1/wallets/{id}` | Update wallet |
| `DELETE /api/v1/wallets/{id}` | Delete wallet |

### Investigations

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/investigations` | Start investigation |
| `GET /api/v1/investigations` | List investigations |
| `GET /api/v1/investigations/{id}` | Get investigation status |
| `PATCH /api/v1/investigations/{id}` | Update investigation |

### Reports

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/reports` | Generate report |
| `GET /api/v1/reports` | List reports |
| `GET /api/v1/reports/{id}` | Get report |
| `GET /api/v1/reports/{id}/download` | Download report |

### AI Investigation Assistant

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/ai/capabilities` | List available AI modes & capabilities |
| `POST /api/v1/ai/query` | Submit a natural-language query |
| `GET /api/v1/ai/query/{task_id}` | Poll query status/result |

### Risk

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/risk/wallets/{wallet_id}/assess` | Assess wallet risk |
| `GET /api/v1/risk/wallets/{wallet_id}/attribution` | Get wallet attribution |
| `POST /api/v1/risk/wallets/{wallet_id}/attribute` | Attribute wallet |
| `GET /api/v1/cases/{case_id}/risk-summary` | Get case risk summary |

### Graph

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/graph?wallet=<id>` | Visualize wallet graph |

---

## 🗂️ Frontend Routes

| Route | Description |
|-------|-------------|
| `/` | Redirects to dashboard |
| `/dashboard` | Main investigator dashboard |
| `/cases` | Case list with filtering |
| `/cases/[caseId]` | Case investigation page |
| `/analyze` | Wallet analysis page |
| `/risk` | Risk assessment page |
| `/ai` | AI Investigation Assistant page |
| `/reports` | Investigation reports |
| `/settings` | Application settings |
| `/graph` | Transaction graph visualization |

---

## 📊 Database Schema

### PostgreSQL Tables

| Table | Description |
|-------|-------------|
| `users` | System users (analysts, supervisors, admins) |
| `cases` | Investigation cases |
| `wallets` | Tracked wallet addresses |
| `transactions` | Blockchain transactions |
| `investigation_runs` | Async investigation jobs |
| `reports` | Generated investigation reports |
| `audit_log` | Audit trail for all investigation actions |

### Neo4j Graph

| Nodes | Relationships |
|-------|-------------|
| `Wallet` — Address, chain, labels, risk scores | `SENT` — Wallet → Transaction |
| `Transaction` — Hash, block, value, timestamps | `RECEIVED` — Transaction → Wallet |
| `Entity` — Known VASPs, mixers, sanctioned addresses | `BELONGS_TO` — Wallet → Entity |
| | Cross-chain edges |

---

## 🧪 Development

### Running Tests

```bash
# Backend tests
cd apps/api
pytest                                    # All tests
pytest -v                                 # Verbose
pytest -k "health"                        # Filter health tests
pytest --cov=src --cov-report=html        # With coverage

# Frontend tests
cd apps/web
npm test                                  # Jest tests
npm run test:watch                        # Watch mode
npm run test:coverage                     # Coverage report
```

### Linting & Type Checking

```bash
# Backend
cd apps/api
ruff check .              # Lint
ruff check . --fix        # Auto-fix lint
mypy .                    # Type check

# Frontend
cd apps/web
npm run lint              # ESLint
npm run typecheck         # TypeScript check (tsc --noEmit)
npm run format            # Prettier
```

### Database Migrations

```bash
cd apps/api

# Create new migration
alembic revision --autogenerate -m "add new table"

# Review generated file in alembic/versions/
# Edit if needed

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🐳 Docker Services

| Service | Port | Description |
|---------|------|-------------|
| frontend | 3000 | Next.js development server |
| backend | 8000 | FastAPI development server |
| postgres | 5432 | PostgreSQL database |
| neo4j | 7474/7687 | Neo4j browser / Bolt |
| redis | 6379 | Redis cache |

### Development

```bash
docker-compose -f docker/docker-compose.yml up -d
docker-compose -f docker/docker-compose.yml logs -f backend
```

### Production

```bash
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

---

## 🏭 Production Deployment

1. **Set `APP_ENV=production`**
2. **Use strong `SECRET_KEY`** (>= 32 chars, generate with `openssl rand -base64 48`)
3. **Configure production database URLs** (postgres, neo4j, redis)
4. **Set up SSL/TLS termination** (Nginx with Let's Encrypt)
5. **Configure proper CORS origins** (restrict to your domain)
6. **Set up monitoring and logging** (Prometheus + Grafana)
7. **Run database migrations** (alembic upgrade head in production container)
8. **Build production images**:

```bash
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

### Post-Deployment Verification

```bash
# Health checks
curl -k https://your-domain.com/api/v1/health
curl -k https://your-domain.com/api/v1/health/ready
curl -k https://your-domain.com/api/v1/health/live

# Frontend
curl -k https://your-domain.com | grep -i "trace-x"

# Database connectivity
docker exec tracex-backend-prod python -c "
from src.core.database import get_session
from sqlalchemy import text
import asyncio
async def test():
    async for s in get_session():
        r = await s.execute(text('SELECT 1'))
        print('DB OK:', r.scalar())
asyncio.run(test())
"

# Neo4j connectivity
docker exec tracex-backend-prod python -c "
from src.graph.client import Neo4jClient
import asyncio
async def test():
    await Neo4jClient.initialize()
    async with Neo4jClient.session() as s:
        r = await s.run('RETURN 1')
        print('Neo4j OK:', await r.consume())
asyncio.run(test())
"

# Redis connectivity
docker exec tracex-redis-prod redis-cli ping
```

---

## 🔒 Security Considerations

- ✅ **Never commit `.env` files** — Only `.env.example` templates are tracked
- ✅ **Use strong, unique secrets** for each environment
- ✅ **Rotate API keys regularly** (blockchain, AI providers)
- ✅ **Enable database SSL in production**
- ✅ **Configure firewall rules** for database ports (restrict to app servers)
- ✅ **Use read-only database users** where possible
- ✅ **Audit log all investigation activities** (audit_log table)
- ⚠️ **No dependency vulnerability scan** run as part of this pass (run `pip-audit`/`npm audit` before production)
- ⚠️ **CSRF protection** is SameSite=Lax only (documented, not pen-tested)

### Secrets Management

- **Local backend dev**: `apps/api/.env` or repo-root `.env` (not tracked in git)
- **Docker dev stack**: Hardcoded dev-only values in compose file (placeholders, not for production)
- **Docker prod stack**: `docker/.env` (Compose reads from `docker/` directory, **not** root `.env.production`)
- **CI**: Repository/organization Secrets, injected as job env vars (never appears in workflow YAML)
- **Never put server-side secrets** in anything that reaches the browser
- **The only frontend env var**: `NEXT_PUBLIC_API_URL` (`apps/web/.env.example`) — Next.js inlines `NEXT_PUBLIC_*` vars at build time

### Secrets Audit (2026-09-03)

**Result: CLEAN** — Only `.env.example`, `apps/web/.env.example`, and `docker/.env.example` are tracked, all contain placeholders only. No committed secrets found in git history.

---

## 📄 License

Proprietary — SIH 2026 Project

---

## 📚 Documentation

| Doc | Description |
|-----|-------------|
| `ARCHITECTURE.md` | System architecture + AI investigation assistant architecture |
| `DEVELOPMENT.md` | Development setup + AI service references + setup commands |
| `EXTERNAL_SERVICES_SETUP.md` | Credential audit table (all providers: required/optional/demo) |
| `KNOWN_LIMITATIONS.md` | Current limitations (AI modes, blockchain, auth, deployment, security) |
| `PRODUCTION_ACCEPTANCE_REPORT.md` | Verification status per category (VERIFIED/PARTIALLY_VERIFIED/etc.) |
| `SECRETS_MANAGEMENT.md` | Secrets locations, setup, audit results (CLEAN — no committed secrets) |
| `SIH_PITCH_DECK.md` | SIH 2026 pitch deck (newly added) |
| `DEMO-SCRIPT.md` | 5-minute demo flow with fallback procedures |
| `runbooks/deployment.md` | Deployment runbook |
| `runbooks/incident-response.md` | Incident response runbook |
| `FINAL_TEST_REPORT.md` | Test execution results |

---

## 🤝 Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feat/amazing-feature`
3. Make changes with tests
4. Run quality checks: `ruff check . && mypy . && npm run lint && npm run typecheck`
5. Commit with conventional messages: `feat: add amazing feature`
6. Push and create PR
7. Address review feedback
8. Merge after approval

---

## 📞 Contact

- **GitHub Issues**: Bug reports, feature requests
- **Discussions**: Architecture questions, design decisions
- **Documentation**: This README + `docs/` folder

---

*TRACE-X — Real-Time Cryptocurrency Fraud Attribution & Investigation Platform — SIH 2026*