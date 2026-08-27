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

### Local Development

```bash
# Clone the repository
git clone https://github.com/koustavx08/trace-x.git
cd trace-x

# Copy environment template
cp .env.example .env

# Start infrastructure
docker-compose -f docker/docker-compose.yml up -d

# Backend
cd apps/api
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd apps/web
npm install
npm run dev
```

## Environment Variables

See `.env.example` for required variables:

- `DATABASE_URL` — PostgreSQL connection string
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — Neo4j connection
- `ALCHEMY_API_KEY` / `INFURA_API_KEY` — Ethereum RPC providers
- `POLYGON_RPC_URL` — Polygon RPC endpoint
- `SECRET_KEY` — Application secret

## License

Proprietary — SIH 2026 Project