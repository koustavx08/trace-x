# TRACE-X Development Setup Guide

## Prerequisites

### Required Software

| Tool | Version | Install Command |
|------|---------|-----------------|
| Git | 2.40+ | `winget install Git.Git` / `brew install git` |
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Docker Compose | 2.20+ | Included with Docker Desktop |
| Node.js | 20 LTS | `winget install OpenJS.NodeJS` / `brew install node@20` |
| Python | 3.11+ | `winget install Python.Python.3.11` / `brew install python@3.11` |
| VS Code | Latest | `winget install Microsoft.VisualStudioCode` / `brew install --cask visual-studio-code` |

### Recommended VS Code Extensions

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "ms-python.black-formatter",
    "charliermarsh.ruff",
    "esbenp.prettier-vscode",
    "bradlc.vscode-tailwindcss",
    "dbaeumer.vscode-eslint",
    "prisma.prisma",
    "ms-azuretools.vscode-docker",
    "github.vscode-github-actions"
  ]
}
```

---

## Quick Start (Docker - Recommended)

### 1. Clone Repository

```bash
git clone https://github.com/koustavx08/trace-x.git
cd trace-x
```

### 2. Configure Environment

```bash
# Copy template
cp .env.example .env

# Edit with your values (at minimum, add API keys)
vim .env
```

**Required for full functionality**:
- `ALCHEMY_API_KEY` - Get from https://alchemy.com
- `INFURA_API_KEY` - Get from https://infura.io

### 3. Start Development Stack

```bash
# Start all services (PostgreSQL, Neo4j, Redis, Backend, Frontend)
docker-compose -f docker/docker-compose.yml up -d

# View logs
docker-compose -f docker/docker-compose.yml logs -f

# Verify services
curl http://localhost:8000/api/v1/health
curl http://localhost:3000
```

### 4. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | - |
| Backend API | http://localhost:8000 | - |
| API Docs | http://localhost:8000/docs | - |
| PostgreSQL | localhost:5432 | tracex/tracex |
| Neo4j Browser | http://localhost:7474 | neo4j/tracexneo4j |
| Redis | localhost:6379 | - |

### 5. Seed Demo Data (Optional)

```bash
# Run demo data seeder (creates 5 SIH cases with synthetic data)
docker exec tracex-backend python scripts/seed_demo_data.py
```

---

## Local Development (Without Docker)

### Backend Setup

```bash
cd apps/api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp ../../.env.example .env
# Edit .env with your values

# Run database migrations
alembic upgrade head

# Start development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Server runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Frontend Setup

```bash
cd apps/web

# Install dependencies
npm install

# Start development server
npm run dev

# Runs at http://localhost:3000
# API requests proxied to http://localhost:8000/api/v1
```

### Running Tests

```bash
# Backend tests
cd apps/api
pytest                    # All tests
pytest -v                 # Verbose
pytest -k "health"        # Filter tests
pytest --cov=src          # With coverage

# Frontend tests
cd apps/web
npm test                  # Jest tests
npm run test:watch        # Watch mode
npm run test:coverage     # Coverage report
```

---

## Project Structure

```
trace-x/
├── apps/
│   ├── api/                 # FastAPI Backend
│   │   ├── src/
│   │   │   ├── core/        # Config, DB, logging, exceptions
│   │   │   ├── models/      # SQLAlchemy models
│   │   │   ├── schemas/     # Pydantic schemas
│   │   │   ├── api/         # API routes (v1)
│   │   │   ├── repositories/# Data access layer
│   │   │   ├── services/    # Business logic
│   │   │   ├── providers/   # Blockchain providers
│   │   │   ├── graph/       # Neo4j graph layer
│   │   │   ├── intelligence/ # Entity intelligence
│   │   │   ├── analytics/   # Risk/attribution engines
│   │   │   ├── reports/     # Report generation
│   │   │   ├── ai/          # AI investigation assistant
│   │   │   └── auth/        # Authentication
│   │   ├── alembic/         # DB migrations
│   │   ├── scripts/         # Utility scripts
│   │   └── tests/           # Unit/integration tests
│   │
│   └── web/                 # Next.js Frontend
│       ├── src/
│       │   ├── app/         # App Router pages
│       │   │   ├── (dashboard)/  # Protected routes
│       │   │   │   ├── dashboard/
│       │   │   │   ├── cases/
│       │   │   │   ├── analyze/
│       │   │   │   ├── graph/
│       │   │   │   ├── risk/
│       │   │   │   ├── ai/
│       │   │   │   ├── reports/
│       │   │   │   └── settings/
│       │   │   └── page.tsx      # Redirect to /dashboard
│       │   ├── components/
│       │   │   └── ui/           # shadcn/ui components
│       │   ├── lib/              # Utilities, API client
│       │   ├── hooks/            # React hooks
│       │   ├── store/            # Zustand stores
│       │   └── types/            # TypeScript types
│       │
│       └── public/               # Static assets
│
├── packages/
│   └── shared/              # Shared TypeScript types
│
├── docker/
│   ├── docker-compose.yml        # Development
│   ├── docker-compose.prod.yml   # Production
│   ├── nginx/                    # SSL termination
│   ├── prometheus/               # Metrics
│   └── grafana/                  # Dashboards
│
├── docs/
│   ├── ARCHITECTURE.md
│   └── runbooks/
│       ├── deployment.md
│       └── incident-response.md
│
├── scripts/                     # Utility scripts
└── .github/workflows/           # CI/CD
```

---

## Key Development Commands

### Backend

```bash
cd apps/api

# Database
alembic upgrade head              # Apply migrations
alembic revision --autogenerate -m "description"  # New migration
alembic downgrade -1              # Rollback one

# Code quality
ruff check .                      # Lint
ruff check . --fix                # Auto-fix lint
mypy .                            # Type check

# Tests
pytest                           # All tests
pytest -v --tb=short             # Verbose
pytest --cov=src --cov-report=html  # Coverage

# Run server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd apps/web

# Development
npm run dev                       # Start dev server

# Build
npm run build                     # Production build
npm run start                     # Start production server

# Code quality
npm run lint                      # ESLint
npm run typecheck                 # TypeScript check

# Tests
npm test                          # Run tests
npm run test:watch                # Watch mode
npm run test:coverage             # Coverage
```

### AI Investigation Assistant

```bash
# AI mode configuration is via APP_ENV and API keys in .env:
#   - AI_MODE=live  - requires ANTHROPIC_API_KEY (or OPENROUTER_API_KEY)
#   - AI_MODE=demo  - works without keys (deterministic templates)
#   - AI_MODE=disabled - AI assistance disabled

# Verify AI setup:
cd apps/api && python scripts/validate_env.py

# AI service endpoints (auto-registered under /api/v1/ai/):
#   GET  /ai/capabilities          - List available AI modes & capabilities
#   POST /ai/query                 - Submit a natural-language query
#   GET  /ai/query/{task_id}       - Poll query status/result

# Test AI query:
curl -X POST http://localhost:8000/api/v1/ai/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the risk score for wallet 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb?", "wallet_id": "wallet-uuid"}'
```

### Docker

```bash
# Development
docker-compose -f docker/docker-compose.yml up -d
docker-compose -f docker/docker-compose.yml logs -f backend
docker-compose -f docker/docker-compose.yml down

# Production
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f
```

---

## API Development

### Adding New Endpoint

1. **Create schema** in `apps/api/src/schemas/__init__.py`
2. **Add model** in `apps/api/src/models/__init__.py` (if needed)
3. **Create repository** in `apps/api/src/repositories/` (if needed)
3. **Create service** in `apps/api/src/services/` (if needed)
4. **Add route** in `apps/api/src/api/v1/<resource>.py`
5. **Register router** in `apps/api/src/api/v1/__init__.py`
6. **Add frontend types** in `apps/web/src/lib/api.ts`
7. **Create API hook** in `apps/web/src/hooks/`

### Database Migrations

```bash
cd apps/api

# Create migration
alembic revision --autogenerate -m "add new table"

# Review generated file in alembic/versions/
# Edit if needed

# Apply
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Adding Blockchain Provider

1. Implement `BlockchainProvider` interface in `apps/api/src/providers/evm/`
2. Register in `apps/api/src/providers/factory.py`
3. Add config in `apps/api/src/core/config.py`
4. Add environment variables in `.env.example`

---

## Frontend Development

### Adding New Page

1. Create route in `apps/web/src/app/(dashboard)/<feature>/page.tsx`
2. Add to navigation in `apps/web/src/app/(dashboard)/layout.tsx`
3. Use shadcn/ui components from `@/components/ui/`
4. Use API client from `@/lib/api/`
5. Use React Query for server state

### Component Guidelines

```tsx
// Use shadcn/ui components
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from "@/components/ui/table"

// Use utility functions
import { formatAddress, formatCurrency, formatRelativeTime } from "@/lib/utils"

// Use Lucide icons
import { Search, Shield, Activity } from "lucide-react"
```

### State Management

- **Server State**: TanStack Query (React Query)
- **Client State**: Zustand (lightweight global)
- **Form State**: React Hook Form + Zod validation

---

## Code Style & Standards

### Python (Backend)

```bash
# Format
ruff format .

# Lint
ruff check .

# Type check
mypy .
```

**Standards**:
- Black formatting (via ruff)
- Type hints required (strict mypy)
- Docstrings for public functions
- Pydantic models for all API schemas
- Structured logging with structlog

### TypeScript (Frontend)

```bash
# Format
npm run format          # Prettier

# Lint
npm run lint            # ESLint

# Type check
npm run typecheck       # tsc --noEmit
```

**Standards**:
- Strict TypeScript
- Functional components + hooks
- Tailwind CSS for styling
- shadcn/ui component library
- React Query for server state

---

## Debugging

### Backend Debugging (VS Code)

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["src.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
      "cwd": "${workspaceFolder}/apps/api",
      "envFile": "${workspaceFolder}/apps/api/.env"
    }
  ]
}
```

### Frontend Debugging (VS Code)

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Next.js",
      "type": "node",
      "request": "launch",
      "command": "npm run dev",
      "cwd": "${workspaceFolder}/apps/web"
    }
  ]
}
```

### Database Debugging

```bash
# PostgreSQL
docker exec -it tracex-postgres psql -U tracex tracex
# Common queries:
# \dt                    # List tables
# \d users              # Describe table
# SELECT * FROM cases;  # Query data

# Neo4j
docker exec -it tracex-neo4j cypher-shell -u neo4j -p tracexneo4j
# Common queries:
# MATCH (n) RETURN count(n);  # Count nodes
# MATCH (w:Wallet) RETURN w LIMIT 10;  # Sample wallets
```

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pip install -e ".[dev]"` in `apps/api` |
| `Port 3000 already in use` | Kill process on 3000 or change port in `package.json` |
| `Port 8000 already in use` | Kill process on 8000 or change in `uvicorn` command |
| `Docker compose up fails` | Run `docker system prune -af` then retry |
| `Database connection refused` | Wait for postgres healthcheck, check `docker logs tracex-postgres` |
| `Neo4j authentication failed` | Verify password in `.env` matches `NEO4J_PASSWORD` |
| `CORS error` | Check `CORS_ORIGINS` in `.env` includes `http://localhost:3000` |
| `JWT token invalid` | Check `SECRET_KEY` matches in `.env` and backend |
| `TypeScript errors` | Run `npm run typecheck` for details |
| `Tailwind styles not applying` | Restart dev server, check `tailwind.config.ts` content paths |

---

## Useful Resources

### Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Next.js 14 Docs](https://nextjs.org/docs)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [shadcn/ui](https://ui.shadcn.com/)
- [TanStack Query](https://tanstack.com/query/latest)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [Alembic](https://alembic.sqlalchemy.org/)

### Blockchain
- [Alchemy Docs](https://docs.alchemy.com/)
- [Infura Docs](https://www.infura.io/docs)
- [EIP-55 Checksum](https://eips.ethereum.org/EIPS/eip-55)

### Monitoring
- [Prometheus](https://prometheus.io/docs/introduction/overview/)
- [Grafana](https://grafana.com/docs/)
- [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/)

---

## Getting Help

- **GitHub Issues**: Bug reports, feature requests
- **Discussions**: Architecture questions, design decisions
- **Discord/Slack**: Real-time chat (invite in repo description)
- **Documentation**: This guide + `docs/` folder

---

## Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feat/amazing-feature`
3. Make changes with tests
4. Run quality checks: `ruff check . && mypy . && npm run lint && npm run typecheck`
5. Commit with conventional messages: `feat: add amazing feature`
6. Push and create PR
6. Address review feedback
7. Merge after approval