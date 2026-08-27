# TRACE-X Incident Response Runbook

## Incident Classification

| Severity | Definition | Response Time | Escalation |
|----------|------------|---------------|------------|
| **SEV-1** | Complete service outage, data loss, security breach | 15 min | Page on-call + manager |
| **SEV-2** | Major functionality degraded, high error rates | 30 min | Page on-call |
| **SEV-3** | Minor functionality issue, non-critical feature | 2 hours | Next business day |
| **SEV-4** | Cosmetic issue, documentation, low impact | Next release | N/A |

---

## Incident Response Process

### 1. Detection & Alert
- Alert fires (Prometheus/Alertmanager/PagerDuty)
- On-call receives notification
- Acknowledge within 5 minutes

### 2. Triage (First 15 minutes)
- [ ] Confirm incident is real (not false positive)
- [ ] Determine severity level
- [ ] Create incident channel (#incident-YYYYMMDD-XXX)
- [ ] Assign Incident Commander (IC)
- [ ] Notify stakeholders per severity

### 3. Investigation
- [ ] Check system health endpoints
- [ ] Review recent deployments/changes
- [ ] Check logs and metrics
- [ ] Identify root cause
- [ ] Document findings in incident channel

### 4. Mitigation
- [ ] Implement immediate fix/workaround
- [ ] Verify fix resolves issue
- [ ] Monitor for regression

### 5. Resolution
- [ ] Confirm service fully restored
- [ ] Close incident in PagerDuty
- [ ] Schedule post-incident review (SEV-1/2 within 48h)

### 6. Post-Incident
- [ ] Write postmortem (template below)
- [ ] Create action items
- [ ] Update runbooks
- [ ] Share learnings

---

## SEV-1 Response Checklist

### Immediate (0-15 min)
- [ ] Page on-call engineer + engineering manager
- [ ] Join incident bridge (Zoom/Teams link in PagerDuty)
- [ ] Declare SEV-1 in #incidents channel
- [ ] Assign roles: IC, Scribe, Communicator, Engineers

### Investigation (15-60 min)
- [ ] Check all health endpoints
- [ ] Review recent deployments (last 24h)
- [ ] Check infrastructure status (AWS/GCP/Azure status pages)
- [ ] Review error logs across all services
- [ ] Check database/Neo4j/Redis connectivity
- [ ] Check blockchain provider status

### Mitigation (60-120 min)
- [ ] Implement workaround (feature flag, rollback, scale)
- [ ] Test workaround in staging if possible
- [ ] Deploy fix to production
- [ ] Verify fix with synthetic transactions

### Communication
- [ ] Update status page every 30 min
- [ ] Notify executive stakeholder (if customer-facing)
- [ ] Prepare customer communication draft (if needed)

---

## Common Incident Scenarios

### Scenario 1: API Returning 5xx Errors

**Symptoms**: Health check fails, users see 500/502/503

**Immediate Checks**:
```bash
# 1. Backend health
curl -v https://tracex.yourdomain.com/api/v1/health

# 2. Container status
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps

# 3. Backend logs (last 100 lines)
docker logs tracex-backend-prod --tail 100 | grep -iE "error|exception|traceback"

# 4. Database connectivity
docker exec tracex-backend-prod python -c "
from src.core.database import get_session
from sqlalchemy import text
import asyncio
async def test():
    async for s in get_session():
        r = await s.execute(text('SELECT 1'))
        print('DB:', r.scalar())
asyncio.run(test())
"
```

**Common Causes & Fixes**:

| Cause | Diagnosis | Fix |
|-------|-----------|-----|
| DB connection pool exhausted | `pool_timeout` in logs, high `active_connections` | Restart backend, increase pool size |
| Neo4j unavailable | `neo4j: disconnected` in health | Restart Neo4j container |
| Redis OOM | `OOM command not allowed` in logs | Restart Redis, check memory |
| Blockchain provider down | Timeout in provider logs | Failover to secondary provider |
| Bad deployment | Errors started after deploy | Rollback to previous version |

**Rollback Procedure**:
```bash
# Quick rollback (last 3 commits)
git log --oneline -5
git checkout HEAD~3
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build backend
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d backend
```

---

### Scenario 2: High Investigation Queue Depth

**Symptoms**: Investigations stuck in `pending`/`running`, queue depth > 100

**Checks**:
```bash
# Queue depth
curl -k https://tracex.yourdomain.com/api/v1/investigations?status=pending,running | jq '.total'

# Worker status
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps worker
docker logs tracex-worker-prod --tail 50
```

**Fixes**:
```bash
# Scale workers
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d --scale worker=6

# Clear stuck investigations (if safe)
curl -X PATCH https://tracex.yourdomain.com/api/v1/investigations/<id> \
  -H "Authorization: Bearer <token>" \
  -d '{"status": "failed", "error_message": "Stale investigation cleared"}'
```

---

### Scenario 3: Neo4j High Memory / OOM

**Symptoms**: Neo4j health check fails, heap usage > 90%, container restarts

**Checks**:
```bash
# Neo4j metrics
curl -k https://tracex.yourdomain.com/api/v1/health | jq '.services.neo4j'

# Container memory
docker stats tracex-neo4j-prod --no-stream

# Neo4j logs
docker logs tracex-neo4j-prod --tail 100 | grep -iE "oom|heap|gc|memory"
```

**Fixes**:
```bash
# 1. Restart Neo4j (clears heap)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart neo4j

# 2. Increase heap (if memory available)
# In docker-compose.prod.yml:
# NEO4J_dbms_memory_heap_max__size: 16g
# Then restart

# 3. Check for runaway queries
docker exec tracex-neo4j-prod cypher-shell -u neo4j -p tracexneo4j "
CALL dbms.listQueries() YIELD queryId, username, metaData, elapsedTimeMillis
WHERE elapsedTimeMillis > 30000
RETURN queryId, username, elapsedTimeMillis, metaData
"

# Kill long-running queries
docker exec tracex-neo4j-prod cypher-shell -u neo4j -p tracexneo4j "
CALL dbms.killQuery('<query-id>')
"
```

---

### Scenario 4: PostgreSQL Connection Pool Exhaustion

**Symptoms**: `pool_timeout` errors, `active_connections` at max, new requests hang

**Checks**:
```bash
# Active connections
docker exec tracex-postgres-prod psql -U tracex -c "
SELECT count(*) as total, state, usename
FROM pg_stat_activity
WHERE datname = 'tracex'
GROUP BY state, usename;
"

# Pool status in backend logs
docker logs tracex-backend-prod --tail 50 | grep -i pool
```

**Fixes**:
```bash
# 1. Kill idle connections
docker exec tracex-postgres-prod psql -U tracex -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'tracex'
  AND state = 'idle'
  AND state_change < now() - interval '10 minutes'
  AND pid <> pg_backend_pid();
"

# 2. Increase pool size (requires restart)
# In .env.production:
# DATABASE_POOL_SIZE=20
# DATABASE_MAX_OVERFLOW=40
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart backend
```

---

### Scenario 5: Blockchain Provider Outage

**Symptoms**: Wallet analysis fails, transaction fetch errors, provider timeouts

**Checks**:
```bash
# Provider health
curl -k https://tracex.yourdomain.com/api/v1/analysis/chains

# Backend logs
docker logs tracex-backend-prod --tail 50 | grep -iE "alchemy|infura|provider|timeout|rpc"
```

**Fixes**:
```bash
# 1. Verify API keys still valid
# 2. Check provider status pages:
#    - https://status.alchemy.com
#    - https://status.infura.io

# 3. Failover to secondary provider (automatic via ProviderFactory)
# 4. If both down: disable wallet analysis, show maintenance banner
```

---

### Scenario 6: Security Incident (Unauthorized Access)

**Symptoms**: Unusual login patterns, audit log anomalies, privilege escalation

**Immediate Actions**:
1. **Contain**: Disable compromised account, revoke tokens
2. **Investigate**: Review audit logs, check IP geo-location
3. **Remediate**: Force password reset, rotate secrets
4. **Notify**: Security team, legal/compliance if required

```bash
# Disable user
docker exec tracex-backend-prod python -c "
from src.models import User
from src.core.database import get_session
from sqlalchemy import select
import asyncio
async def disable():
    async for s in get_session():
        result = await s.execute(select(User).where(User.email == 'compromised@domain.com'))
        user = result.scalar_one_or_none()
        if user:
            user.is_active = False
            await s.commit()
            print('User disabled')
asyncio.run(disable())
"

# Revoke all tokens (change JWT secret)
# 1. Generate new secret
# 2. Update in secrets manager
# 3. Restart all backend instances
```

---

## Communication Templates

### Internal Status Update (Every 30 min during SEV-1)

```
**INCIDENT UPDATE** - [SEV-1] API Outage
**Time**: 2024-01-15 14:30 UTC
**Status**: Investigating
**Impact**: All API endpoints returning 500
**Root Cause**: Unknown (suspected DB connection pool)
**Actions Taken**: 
- Rolled back backend to v1.2.3
- Scaled DB connections
**Next Update**: 15:00 UTC
**IC**: @engineer-name
```

### Customer Notification (If Required)

```
Subject: TRACE-X Service Disruption - [Date]

Dear Customer,

We are experiencing a service disruption affecting [specific functionality].
Our engineering team is actively investigating and working on a resolution.

Impact: [Description of user-facing impact]
Started: [Timestamp]
Estimated Resolution: [Time or "under investigation"]

We will provide updates every 30 minutes via [status page / email].
We apologize for the inconvenience.

TRACE-X Operations Team
```

---

## Postmortem Template

```
# Postmortem: [Incident Title]

**Date**: 2024-01-15
**Duration**: 45 minutes (14:30 - 15:15 UTC)
**Severity**: SEV-1
**Author**: [Name]
**Reviewers**: [Names]

## Summary
Brief 2-3 sentence summary of what happened.

## Timeline
| Time (UTC) | Event |
|------------|-------|
| 14:30 | Alert fired: API health check failing |
| 14:32 | On-call paged, joined bridge |
| 14:35 | IC assigned, severity declared SEV-1 |
| 14:40 | Root cause identified: DB connection pool exhaustion |
| 14:45 | Rolled back backend to v1.2.3 |
| 14:50 | Health checks passing |
| 15:00 | Verified with synthetic transactions |
| 15:15 | Incident resolved, monitoring |

## Root Cause
Primary: Connection pool exhaustion due to [specific reason]
Contributing: [Any contributing factors]

## Impact
- **Users affected**: ~500 investigators
- **Investigations delayed**: 23
- **Data loss**: None
- **Revenue impact**: N/A

## What Went Well
- Alert fired quickly
- On-call responded within 2 min
- Rollback procedure worked
- Communication was clear

## What Went Wrong
- Connection pool monitoring alert was missing
- No automatic scaling for DB connections
- Rollback took 10 min (manual process)

## Action Items
| # | Action | Owner | Due Date | Status |
|---|--------|-------|----------|--------|
| 1 | Add DB connection pool alert | @devops | 2024-01-22 | Open |
| 2 | Implement auto-scaling for DB pool | @backend | 2024-01-29 | Open |
| 3 | Automate rollback procedure | @devops | 2024-02-05 | Open |
| 4 | Add synthetic transaction monitoring | @platform | 2024-01-22 | Open |

## Lessons Learned
- Need better connection pool observability
- Manual rollback too slow for SEV-1
- Runbook needs update for DB pool exhaustion

## Supporting Data
- [Grafana dashboard link]
- [Log excerpts]
- [Metrics screenshots]
```

---

## Escalation Contacts

| Role | Name | Phone | Slack | PagerDuty |
|------|------|-------|-------|-----------|
| Primary On-Call | | | @ | |
| Secondary On-Call | | | @ | |
| Engineering Manager | | | @ | |
| Platform Lead | | | @ | |
| Security Officer | | | @ | |
| Legal/Compliance | | | @ | |

---

## Runbook Maintenance

- **Review Frequency**: Monthly
- **Owner**: Platform Team
- **Last Reviewed**: [Date]
- **Next Review**: [Date + 30 days]

### Update Process
1. Edit this document
2. Create PR with changes
3. Review by Platform Team
4. Merge and notify team