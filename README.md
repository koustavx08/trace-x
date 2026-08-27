# TRACE-X

**Real-Time Cryptocurrency Fraud Attribution & Investigation Platform**

> SIH26183 — Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported Suspect Wallet Addresses through Automated Blockchain Analytics.

## Overview

TRACE-X is an investigation and intelligence platform for cybercrime investigators and authorized law-enforcement analysts. It traces cryptocurrency fund flows from suspect wallet addresses through intermediary wallets to identify the nearest probable VASP/exchange, providing explainable evidence and confidence levels for every attribution.

**This is NOT a cryptocurrency exchange.** It does not perform transactions, custody funds, or interact with private keys.

## Core User Flow

1. Investigator creates or selects a case
2. Investigator enters a suspect cryptocurrency wallet address
3. System validates the address and identifies the blockchain
4. TRACE-X fetches relevant blockchain transactions
5. TRACE-X recursively traces outgoing fund flows through intermediary wallets
6. TRACE-X constructs a transaction graph
7. TRACE-X detects suspicious movement patterns
8. TRACE-X checks known entity intelligence and VASP/exchange labels
9. TRACE-X calculates an explainable risk score
10. TRACE-X identifies the nearest probable VASP/exchange reached by the traced flow
11. TRACE-X shows evidence and confidence rather than claiming certainty
12. TRACE-X generates an investigation report

## Confidence Levels

- **CONFIRMED** — Verified on-chain + off-chain correlation
- **HIGH_CONFIDENCE** — Strong heuristic + multiple corroborating signals
- **PROBABLE** — Single strong signal or multiple weak signals
- **UNKNOWN** — Insufficient evidence

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Zustand, React Flow |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy |
| Database | PostgreSQL (application data), Neo4j (transaction graph) |
| Infrastructure | Docker Compose, Environment variables |
| Blockchain | Ethereum (primary), Polygon (secondary), EVM-compatible abstraction layer |
| Analytics | NetworkX, rule-based detection, optional ML modules |

## Project Structure

```
trace-x/
├── apps/
│   ├── web/          # Next.js frontend
│   └── api/          # FastAPI backend
├── packages/
│   └── shared/       # Shared types, schemas, utilities
├── docker/           # Docker Compose configurations
├── scripts/          # Utility scripts
└── docs/             # Documentation
```

## Getting Started

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

## Environment Variables

See `.env.example` for all required variables:

### Application
- `APP_ENV` — Environment (development/production)
- `SECRET_KEY` — Application secret key (min 32 chars)
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

### Entity Intelligence
- `CHAINALYSIS_API_KEY` — Chainalysis API key
- `CIPHERTRACE_API_KEY` — CipherTrace API key
- `OFAC_SDN_LIST_URL` — OFAC SDN list URL

### Logging
- `LOG_LEVEL` — Log level (DEBUG/INFO/WARNING/ERROR)
- `LOG_FORMAT` — Log format (json/text)

## API Endpoints

### Health
- `GET /api/v1/health` — Health check with service status
- `GET /api/v1/health/ready` — Readiness probe
- `GET /api/v1/health/live` — Liveness probe

### Cases
- `POST /api/v1/cases` — Create case
- `GET /api/v1/cases` — List cases (paginated, filterable)
- `GET /api/v1/cases/{id}` — Get case details
- `PATCH /api/v1/cases/{id}` — Update case
- `DELETE /api/v1/cases/{id}` — Delete case

### Wallets
- `POST /api/v1/wallets` — Add wallet to case
- `GET /api/v1/wallets` — List wallets (paginated, filterable)
- `GET /api/v1/wallets/{id}` — Get wallet details
- `PATCH /api/v1/wallets/{id}` — Update wallet
- `DELETE /api/v1/wallets/{id}` — Delete wallet

### Investigations
- `POST /api/v1/investigations` — Start investigation
- `GET /api/v1/investigations` — List investigations
- `GET /api/v1/investigations/{id}` — Get investigation status
- `PATCH /api/v1/investigations/{id}` — Update investigation

### Reports
- `POST /api/v1/reports` — Generate report
- `GET /api/v1/reports` — List reports
- `GET /api/v1/reports/{id}` — Get report

## Frontend Routes

| Route | Description |
|-------|-------------|
| `/` | Redirects to dashboard |
| `/dashboard` | Main investigator dashboard |
| `/cases` | Case list with filtering |
| `/cases/[caseId]` | Case investigation page |
| `/analyze` | Wallet analysis page |
| `/reports` | Investigation reports |
| `/settings` | Application settings |

## Database Schema

### PostgreSQL Tables
- `users` — System users (analysts, supervisors, admins)
- `cases` — Investigation cases
- `wallets` — Tracked wallet addresses
- `transactions` — Blockchain transactions
- `investigation_runs` — Async investigation jobs
- `reports` — Generated investigation reports

### Neo4j Graph
- `Wallet` nodes — Address, chain, labels, risk scores
- `Transaction` nodes — Hash, block, value, timestamps
- `Entity` nodes — Known VASPs, mixers, sanctioned addresses
- Relationships: `SENT`, `RECEIVED`, `BELONGS_TO`

## Development

### Running Tests

```bash
# Backend tests
cd apps/api
pytest

# Frontend tests
cd apps/web
npm test
```

### Linting & Type Checking

```bash
# Backend
cd apps/api
ruff check .
mypy .

# Frontend
cd apps/web
npm run lint
npm run typecheck
```

### Database Migrations

```bash
cd apps/api

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| frontend | 3000 | Next.js development server |
| backend | 8000 | FastAPI development server |
| postgres | 5432 | PostgreSQL database |
| neo4j | 7474/7687 | Neo4j browser / Bolt |
| redis | 6379 | Redis cache |

## Production Deployment

1. Set `APP_ENV=production`
2. Use strong `SECRET_KEY`
3. Configure production database URLs
4. Set up SSL/TLS termination
5. Configure proper CORS origins
6. Set up monitoring and logging
7. Run database migrations
8. Build production images:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
   ```

## Security Considerations

- Never commit `.env` files
- Use strong, unique secrets for each environment
- Rotate API keys regularly
- Enable database SSL in production
- Configure firewall rules for database ports
- Use read-only database users where possible
- Audit log all investigation activities

## License

Proprietary — SIH 2026 Project