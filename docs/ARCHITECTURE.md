# TRACE-X Architecture Documentation

## Overview

TRACE-X is a Real-Time Cryptocurrency Fraud Attribution & Investigation Platform designed for cybercrime investigators and law enforcement analysts. It traces cryptocurrency fund flows from suspect wallet addresses through intermediary wallets to identify the nearest probable VASP/exchange.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TRACE-X PLATFORM                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │   FRONTEND   │    │    BACKEND   │    │   DATABASE   │    │  GRAPH   │  │
│  │  (Next.js)   │◄──►│  (FastAPI)   │◄──►│  (PostgreSQL)│    │ (Neo4j)  │  │
│  │  Port 3000   │    │  Port 8000   │    │  Port 5432   │    │ Port7687 │  │
│  └──────────────┘    └──────┬───────┘    └──────────────┘    └──────────┘  │
│                             │                                                │
│                    ┌────────┴────────┐    ┌──────────────┐    ┌──────────┐  │
│                    │  BLOCKCHAIN     │    │    CACHE     │    │ MONITOR  │  │
│                    │  PROVIDERS      │    │   (Redis)    │    │ (Prom/Graf)│ │
│                    │ (Alchemy/Infura)│    │  Port 6379   │    │ 9090/3001│  │
│                    └─────────────────┘    └──────────────┘    └──────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### Frontend (Next.js 14)
- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui
- **State Management**: TanStack Query + Zustand
- **Visualization**: React Flow (graph), Recharts (charts)
- **Authentication**: JWT with HttpOnly cookies

### Backend (FastAPI)
- **Framework**: FastAPI with async support
- **Language**: Python 3.11+
- **Database ORM**: SQLAlchemy 2.0 (async)
- **Graph Database**: Neo4j with async driver
- **Authentication**: JWT (RS256) with refresh tokens
- **Rate Limiting**: Redis-backed sliding window
- **Logging**: Structured JSON with structlog

### Database (PostgreSQL 15)
- **Tables**: users, cases, wallets, transactions, investigation_runs, reports, audit_logs
- **Migrations**: Alembic
- **Connection Pool**: AsyncPG with 10-30 connections

### Graph Database (Neo4j 5.15)
- **Nodes**: Wallet, Transaction, Entity
- **Relationships**: SENT, RECEIVED, BELONGS_TO
- **Plugins**: APOC, Graph Data Science
- **Indexes**: Wallet(address, chain), Transaction(tx_hash), Entity(address, chain)

### Blockchain Providers
- **Primary**: Alchemy (Ethereum, Polygon)
- **Fallback**: Infura
- **Interface**: Abstract provider pattern for extensibility
- **Rate Limiting**: Built-in with exponential backoff

### Cache (Redis 7)
- **Use Cases**: Session storage, API response caching, rate limiting, Celery broker
- **Configuration**: LRU eviction, 512MB max

## Data Flow

### Wallet Analysis Pipeline
```
1. User submits wallet address + case ID
2. Backend validates address (EIP-55 checksum)
3. Detects blockchain (Ethereum/Polygon)
4. Fetches transactions via Alchemy API
5. Stores in PostgreSQL + Neo4j
6. Runs risk scoring engine
7. Performs graph traversal to VASPs
8. Returns results to frontend
```

### Risk Scoring
- 12 risk factors with weighted scoring
- Confidence propagation (CONFIRMED/HIGH_CONFIDENCE/PROBABLE/UNKNOWN)
- Severity: CRITICAL≥80, HIGH≥60, MEDIUM≥40, LOW≥20, INFO<20

### VASP Attribution
- Dijkstra shortest-path to known entities
- Attribution types: DIRECT, INDIRECT, CLUSTER, HEURISTIC
- Confidence scoring with path penalty + type weights

## Security

### Authentication
- JWT with RS256 (access: 30min, refresh: 7 days)
- Bcrypt password hashing (12 rounds)
- Role-based access: admin > supervisor > analyst

### Network Security
- TLS 1.2/1.3 only
- HSTS, CSP, X-Frame-Options headers
- Rate limiting: 100 req/s (API), 5 req/min (login)
- CORS restricted to configured origins

### Data Protection
- No private keys stored
- No transaction signing capability
- Audit logging for all investigation actions
- Encrypted secrets via environment variables

## Deployment

### Development
```bash
docker-compose -f docker/docker-compose.yml up -d
```

### Production
```bash
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

### Environment Variables
See `.env.example` for all required variables.

## Monitoring & Observability

### Metrics (Prometheus)
- HTTP request rate/latency/error rate
- Investigation job queue depth
- Database connection pool usage
- Neo4j heap/cache usage
- Custom business metrics (investigations, wallet analyses)

### Logging
- Structured JSON logs
- Correlation IDs for request tracing
- Audit logs for all investigation actions
- Log levels: DEBUG, INFO, WARN, ERROR

### Alerting Rules
- API error rate > 5%
- p99 latency > 5s
- Investigation queue depth > 100
- Database connections > 80%
- Neo4j heap > 85%

## Disaster Recovery

### Backups
- PostgreSQL: Daily pg_dump, WAL archiving
- Neo4j: Daily incremental, weekly full
- Configuration: GitOps (version controlled)

### RPO/RTO
- RPO: 1 hour (database), 24 hours (graph)
- RTO: 4 hours (full restore)

## Compliance

- **Data Classification**: All investigation data marked CONFIDENTIAL
- **Audit Trail**: Immutable audit log for all actions
- **Chain of Custody**: Hash-linked evidence records
- **No Private Keys**: Platform never handles private keys
- **No Custody**: No funds held or transferred