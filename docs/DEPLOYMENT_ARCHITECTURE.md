# Deployment Architecture

## Recommendation

For TRACE-X's actual footprint — a FastAPI backend, Next.js frontend, Postgres, Redis, Neo4j, Celery worker+beat, and
a Prometheus/Grafana stack that's entirely optional at demo scale — the simplest reliable path is:

| Component | Recommended target | Why |
|---|---|---|
| Frontend (Next.js) | **Vercel** | Zero-config for Next.js `output: 'standalone'` builds, generous free tier, instant preview deploys per PR. |
| Backend + worker + beat (FastAPI/Celery) | **Railway** or **Fly.io** (containers) | Both run the existing `Dockerfile.prod` images unmodified, support long-running worker processes (unlike most serverless platforms), and have usable free/hobby tiers. |
| PostgreSQL | **Neon** or **Railway Postgres** (managed) | Free tier, automated backups, no volume/ops burden — avoids self-hosting a stateful DB. |
| Redis | **Upstash** or **Railway Redis** (managed) | Free tier sufficient for Celery + chat sessions + JTI blacklist at demo/pilot scale. |
| Neo4j | **Neo4j AuraDB Free** | Purpose-built managed Neo4j; self-hosting Neo4j (12 GB memory limits in `docker-compose.prod.yml`) is the single heaviest, most ops-intensive piece of this stack to run yourself. |
| Monitoring | **Keep the existing Prometheus/Grafana compose stack**, self-hosted on the same host as the backend (or skip entirely for a pilot/demo) | It's already built and wired to real metrics (`/api/v1/metrics`, Neo4j's Prometheus exporter); a managed alternative (Grafana Cloud free tier) is a reasonable upgrade later but isn't required to be "production ready." |

This trades the fully self-hosted `docker-compose.prod.yml` stack for managed infra on the stateful pieces
(Postgres/Redis/Neo4j) while keeping the app containers portable — the same `Dockerfile.prod` images work
unchanged on Railway/Fly/a bare VM/the existing Compose file. Nothing here requires a code change; it's purely
where each already-configurable `*_URL` / credential points.

## Evaluation

| Factor | Self-hosted Docker Compose (current) | Recommended managed mix |
|---|---|---|
| Cost at pilot scale | Server cost only, but you pay in ops time | Free tiers cover a pilot/demo; scales to paid tiers predictably |
| Free-tier limitations | N/A (you own the box) | Neon/Upstash/Aura free tiers cap storage/connections — fine for a case-load demo, revisit before real investigator volume |
| Persistent storage | Named Docker volumes on one host — a host failure loses data without a separate backup process | Managed providers handle durability/backups by default |
| Docker support | Native — this *is* the Docker path | Backend/worker still ship as the same Docker images; only the databases move off-container |
| Network access | All services on one Docker network, simplest to reason about | Backend needs outbound network access to 3 managed endpoints (Postgres, Redis, Neo4j) — all standard TLS connections, no special firewall work |
| Secret management | `docker/.env`, manually protected | Platform-native secret stores (Railway/Fly/Vercel env vars) — one less way to leak a `.env` file |
| Neo4j compatibility | Full control (APOC/GDS plugins, exact version) | AuraDB Free supports APOC; GDS (graph-data-science) is **not** available on AuraDB Free — if pattern-detection queries lean on GDS procedures beyond APOC, verify this before committing to Aura Free, or self-host just Neo4j while managing Postgres/Redis |
| Demo/pilot reliability | You are the single point of failure for uptime during a demo | Managed platforms remove "is my laptop/VM still running" as a demo-day risk |
| Deployment simplicity | One `docker compose up` once secrets are set | A few platform dashboards instead of one, but each is simpler individually (push-to-deploy, no server patching) |

**Caveat on Neo4j/GDS**: this repository's `docker-compose.prod.yml` requests `NEO4J_PLUGINS: '["apoc", "graph-data-science"]'`.
Before moving Neo4j to AuraDB Free, grep `apps/api/src/graph/queries.py` for any GDS-specific procedure calls
(`gds.*`) — if present, either keep Neo4j self-hosted (Docker Compose, unchanged) or use a paid Aura tier that
includes GDS. This wasn't verified against a live Aura instance as part of this pass; treat it as the one open
question before adopting the managed-Neo4j recommendation.

## What does not need to move

Nothing about the recommendation above requires touching application code: every target is reached purely through
`DATABASE_URL` / `REDIS_URL` / `NEO4J_URI` / `NEXT_PUBLIC_API_URL` already being environment-driven. The existing
`docker-compose.prod.yml` fully self-hosted path remains valid and is what CI's "Docker Compose Validation" workflow
checks — choose it over the managed mix if you'd rather not split state across three vendors, e.g. for an
air-gapped or fully self-hosted deployment requirement.
