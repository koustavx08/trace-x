# TRACE-X Deployment Runbook

## Quick Reference

| Item | Value |
|------|-------|
| **Repository** | https://github.com/koustavx08/trace-x |
| **Main Branch** | `main` |
| **Docker Registry** | GitHub Container Registry (ghcr.io) |
| **Production Domain** | tracex.yourdomain.com |
| **Monitoring** | Grafana: https://grafana.yourdomain.com |
| **On-Call** | See PagerDuty schedule |

---

## Pre-Deployment Checklist

- [ ] All CI checks pass (lint, typecheck, tests)
- [ ] Database migrations reviewed and tested
- [ ] Environment variables configured in `docker/.env` (see `docs/SECRETS_MANAGEMENT.md`), validated with `python apps/api/scripts/validate_env.py`
- [ ] SSL certificates obtained (Let's Encrypt or paid)
- [ ] DNS records updated (A record for domain)
- [ ] Secrets rotated (JWT secret, DB passwords, API keys)
- [ ] Backup verified (test restore completed)
- [ ] Rollback plan documented
- [ ] Stakeholders notified of maintenance window

---

## Environment Setup

### Required Secrets (Store in Vault/Secrets Manager)

```bash
# Application
# Auth signs JWTs with HS256 and this one symmetric secret (src/auth/__init__.py)
# -- there is no RSA keypair anywhere in this app; don't generate one.
SECRET_KEY=<64-char-random-string>

# Database
DATABASE_URL=postgresql+asyncpg://tracex:<password>@postgres:5432/tracex
NEO4J_PASSWORD=<strong-password>

# Blockchain Providers
ALCHEMY_API_KEY=<key>
INFURA_API_KEY=<key>
INFURA_API_SECRET=<secret>
ETHEREUM_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/<key>
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/<key>

# Redis
REDIS_URL=redis://redis:6379/0

# External APIs
CHAINALYSIS_API_KEY=<key>
CIPHERTRACE_API_KEY=<key>

# Monitoring
GRAFANA_ADMIN_PASSWORD=<password>
```

### Generate Secrets

```bash
# Generate SECRET_KEY / DB passwords
openssl rand -base64 48
```

See `docs/EXTERNAL_SERVICES_SETUP.md` for every external credential the app actually reads (which are required vs.
optional, and what degrades gracefully without each), and `docs/SECRETS_MANAGEMENT.md` for where each `.env` file
belongs and how to validate one before deploying.

---

## Development Deployment

### Prerequisites
- Docker 24+ & Docker Compose 2.20+
- Node.js 20+ (for local frontend dev)
- Python 3.11+ (for local backend dev)
- Git

### Start Development Stack

```bash
# Clone repository
git clone https://github.com/koustavx08/trace-x.git
cd trace-x

# Copy environment template
cp .env.example .env

# Edit .env with your values
vim .env

# Start all services
docker-compose -f docker/docker-compose.yml up -d

# Verify services
curl http://localhost:8000/api/v1/health
curl http://localhost:3000

# View logs
docker-compose -f docker/docker-compose.yml logs -f backend
docker-compose -f docker/docker-compose.yml logs -f frontend
```

### Local Development (Without Docker)

```bash
# Backend
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd apps/web
npm install
npm run dev
```

---

## Production Deployment

### Server Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 16 GB | 32+ GB |
| Disk | 100 GB SSD | 500 GB NVMe |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

### Initial Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose v2
sudo apt install docker-compose-plugin

# Configure firewall
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 3001/tcp  # Grafana (restrict to VPN)
sudo ufw allow 9090/tcp  # Prometheus (restrict to VPN)
sudo ufw enable

# Configure swap (if RAM < 32GB)
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Deploy Production Stack

```bash
# Clone repository
git clone https://github.com/koustavx08/trace-x.git
cd trace-x
git checkout main

# Create production environment
# docker-compose.prod.yml's ${VAR} substitution reads docker/.env by default
# (Compose's project directory is the folder of the first -f file below,
# which is docker/ for both compose files in this repo) -- NOT a root
# .env.production. See docs/SECRETS_MANAGEMENT.md.
cp docker/.env.example docker/.env
vim docker/.env  # Fill in all production values
cd apps/api && python scripts/validate_env.py && cd ../..  # verify before deploying

# Obtain SSL certificates (Let's Encrypt)
sudo apt install certbot
sudo certbot certonly --standalone -d tracex.yourdomain.com
# Certificates will be in /etc/letsencrypt/live/tracex.yourdomain.com/
# Copy to docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/tracex.yourdomain.com/fullchain.pem docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/tracex.yourdomain.com/privkey.pem docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/tracex.yourdomain.com/chain.pem docker/nginx/ssl/
sudo chown -R $USER:$USER docker/nginx/ssl/

# Start production stack
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d

# Verify deployment
curl -k https://tracex.yourdomain.com/api/v1/health
curl -k https://tracex.yourdomain.com

# Check all containers healthy
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps
```

### Verify Production Deployment

```bash
# Health checks
curl -k https://tracex.yourdomain.com/api/v1/health
curl -k https://tracex.yourdomain.com/api/v1/health/ready
curl -k https://tracex.yourdomain.com/api/v1/health/live

# Frontend
curl -k https://tracex.yourdomain.com | grep -i "trace-x"

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

## SSL Certificate Management

### Let's Encrypt Auto-Renewal

```bash
# Test renewal
sudo certbot renew --dry-run

# Add cron job
echo "0 3 * * * root certbot renew --quiet && cp /etc/letsencrypt/live/tracex.yourdomain.com/*.pem /path/to/trace-x/docker/nginx/ssl/ && docker-compose -f /path/to/trace-x/docker/docker-compose.yml -f /path/to/trace-x/docker/docker-compose.prod.yml restart nginx" | sudo tee /etc/cron.d/certbot-renew
```

### Manual Certificate Update

```bash
# Copy new certificates
sudo cp /etc/letsencrypt/live/tracex.yourdomain.com/fullchain.pem docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/tracex.yourdomain.com/privkey.pem docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/tracex.yourdomain.com/chain.pem docker/nginx/ssl/

# Reload nginx
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart nginx
```

---

## Database Operations

### Run Migrations

```bash
# Development
cd apps/api
alembic upgrade head

# Production (via container)
docker exec tracex-backend-prod alembic upgrade head
```

### Create New Migration

```bash
cd apps/api
alembic revision --autogenerate -m "description of changes"
# Review generated file in alembic/versions/
alembic upgrade head
```

### Backup Database

```bash
# PostgreSQL backup
docker exec tracex-postgres-prod pg_dump -U tracex tracex > backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
docker exec tracex-postgres-prod pg_dump -U tracex tracex | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Restore
gunzip -c backup_20240115_120000.sql.gz | docker exec -i tracex-postgres-prod psql -U tracex tracex
```

### Neo4j Backup

```bash
# Online backup (requires enterprise)
docker exec tracex-neo4j-prod neo4j-admin backup --backup-dir=/backups --name=tracex-$(date +%Y%m%d)

# Or use neo4j-admin dump (community)
docker exec tracex-neo4j-prod neo4j-admin database dump neo4j --to-path=/backups
```

---

## Scaling Operations

### Horizontal Scaling (Backend Workers)

```bash
# Scale worker replicas
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d --scale worker=4

# Check worker status
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps worker
```

### Database Connection Pooling

```bash
# Adjust in docker/.env
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
```

### Neo4j Memory Tuning

```bash
# In docker-compose.prod.yml
NEO4J_dbms_memory_heap_initial__size: 4g
NEO4J_dbms_memory_heap_max__size: 16g
NEO4J_dbms_memory_pagecache_size: 8g
```

---

## Monitoring & Alerting

### Access Grafana

```bash
# URL: https://grafana.yourdomain.com
# Username: admin
# Password: from GRAFANA_ADMIN_PASSWORD secret
```

### Key Dashboards

1. **TRACE-X Overview** - System health, API metrics, investigation throughput
2. **Database** - PostgreSQL/Neo4j performance
3. **Investigations** - Case throughput, risk distribution, attribution rates
4. **AI Assistant** - Query volume, confidence distribution

### Critical Alerts

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| API Down | Health check fails | Critical | Page on-call immediately |
| High Error Rate | >5% 5xx errors | Critical | Check logs, restart if needed |
| High Latency | p99 > 5s | Warning | Check DB/Neo4j load |
| DB Connections | >80% pool used | Warning | Scale or optimize queries |
| Neo4j Heap | >85% used | Warning | Restart Neo4j, check queries |
| Disk Space | >85% used | Warning | Clean logs, expand disk |

### Silencing Alerts

```bash
# Via Alertmanager (if configured)
amtool silence add --duration=2h --author="runbook" --comment="Planned maintenance" alertname="HighLatency"
```

---

## Incident Response

### Common Incidents

#### API Returning 500 Errors
```bash
# Check backend logs
docker logs tracex-backend-prod --tail 100 | grep -i error

# Check database connectivity
docker exec tracex-backend-prod python -c "from src.core.database import get_session; from sqlalchemy import text; import asyncio; asyncio.run(get_session().__anext__().execute(text('SELECT 1')))"

# Restart backend if needed
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart backend
```

#### High Investigation Queue Depth
```bash
# Check running investigations
curl -k https://tracex.yourdomain.com/api/v1/investigations?status=running

# Scale workers
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d --scale worker=6
```

#### Neo4j High Memory
```bash
# Check Neo4j metrics
curl -k https://tracex.yourdomain.com/api/v1/health

# Restart Neo4j (will lose in-memory cache)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart neo4j
```

### Post-Incident

1. Document timeline in incident report
2. Root cause analysis within 48 hours
3. Action items tracked in GitHub Issues
4. Runbook updated if new scenario

---

## Rollback Procedures

### Application Rollback

```bash
# Tag current deployment
git tag rollback-$(date +%Y%m%d-%H%M%S)

# Checkout previous stable release
git checkout v1.2.3  # or previous commit hash

# Rebuild and deploy
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

### Database Rollback

```bash
# If migration caused issues
cd apps/api
alembic downgrade -1  # Rollback one migration

# Or restore from backup
gunzip -c backup_20240115_120000.sql.gz | docker exec -i tracex-postgres-prod psql -U tracex tracex
```

### Full System Rollback

```bash
# 1. Stop all services
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down

# 2. Restore databases from backup
# PostgreSQL
gunzip -c backup_20240115_120000.sql.gz | docker exec -i tracex-postgres-prod psql -U tracex tracex
# Neo4j (restore from dump)
docker exec tracex-neo4j-prod neo4j-admin database load neo4j --from-path=/backups/tracex-20240115

# 3. Deploy previous version
git checkout v1.2.3
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

---

## Security Operations

### Secret Rotation (Monthly)

```bash
# Rotate JWT keys
openssl genrsa -out jwt_private.pem.new 2048
openssl rsa -in jwt_private.pem.new -pubout -out jwt_public.pem.new
# Update in secrets manager
# Restart backend

# Rotate database password
# 1. Generate new password
# 2. Update in PostgreSQL: ALTER USER tracex PASSWORD 'newpass'
# 3. Update POSTGRES_PASSWORD in docker/.env
# 4. Restart backend
```

### Audit Log Review

```bash
# Export audit logs for review
docker exec tracex-backend-prod python -c "
from src.models import AuditLog
from sqlalchemy import select
from src.core.database import get_session
import asyncio

async def export():
    async for s in get_session():
        result = await s.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(1000))
        for log in result.scalars():
            print(f'{log.timestamp} | {log.user_email} | {log.action} | {log.resource_type} | {log.success}')
asyncio.run(export())
" > audit_logs_$(date +%Y%m%d).txt
```

---

## Performance Tuning

### Slow Query Analysis

```bash
# Enable pg_stat_statements in PostgreSQL
docker exec tracex-postgres-prod psql -U tracex -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

# Top 10 slowest queries
docker exec tracex-postgres-prod psql -U tracex -c "
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
"
```

### Neo4j Query Optimization

```bash
# Enable query logging
# In neo4j.conf: dbms.logs.query.enabled=true
# dbms.logs.query.threshold=1000ms

# Check slow queries in /logs/query.log
docker exec tracex-neo4j-prod tail -f /logs/query.log
```

---

## Maintenance Windows

### Scheduled Maintenance

- **Weekly**: Sunday 02:00-04:00 UTC (low traffic)
- **Monthly**: First Sunday 00:00-06:00 UTC (full maintenance)
- **Quarterly**: Full DR test

### Maintenance Tasks

| Task | Frequency | Command |
|------|-----------|---------|
| Log rotation | Daily | Automatic (Docker) |
| SSL renewal | Monthly | `certbot renew` |
| DB vacuum | Weekly | `pg_dump --clean` |
| Neo4j checkpoint | Daily | Automatic |
| Secret rotation | Monthly | Manual (see above) |
| Dependency updates | Monthly | `dependabot` PRs |
| Backup verification | Weekly | Test restore |

---

## Contacts

| Role | Name | Contact |
|------|------|---------|
| Platform Owner | | |
| Lead Engineer | | |
| DevOps Engineer | | |
| Security Officer | | |
| On-Call Primary | | PagerDuty |
| On-Call Secondary | | PagerDuty |

---

## Appendix: Useful Commands

```bash
# View all container logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f --tail=100

# Execute command in container
docker exec -it tracex-backend-prod bash
docker exec -it tracex-postgres-prod psql -U tracex tracex
docker exec -it tracex-neo4j-prod cypher-shell -u neo4j -p tracexneo4j

# Resource usage
docker stats --no-stream

# Clean up unused Docker resources
docker system prune -af --volumes

# Export environment for debugging
docker exec tracex-backend-prod env | sort
```