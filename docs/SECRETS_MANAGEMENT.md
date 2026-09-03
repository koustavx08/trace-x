# Secrets Management

## Where secrets live

| Context | File | Tracked in git? |
|---|---|---|
| Local backend dev (`uvicorn` run directly) | `apps/api/.env` or repo-root `.env` (pydantic-settings reads `.env` from cwd) | No |
| `docker compose -f docker/docker-compose.yml` (dev stack) | Hardcoded dev-only values in the compose file itself (e.g. `SECRET_KEY: dev-secret-key-not-for-production-use-only-min-32-chars`) | Yes — intentionally, these are non-secret dev placeholders, never used in production |
| `docker compose -f docker/docker-compose.prod.yml` | `docker/.env` (Compose's project directory defaults to the directory of the first `-f` file, i.e. `docker/`) | No |
| CI (GitHub Actions) | Repository/organization *Secrets*, injected as job env vars | No — never appears in workflow YAML as a literal value |
| A managed deployment platform (Render/Railway/Fly/Vercel/etc.) | That platform's own environment-variable/secret store | No |

Templates (`*.example` files) are the only tracked variants:
`.env.example`, `apps/web/.env.example`, `docker/.env.example`. All three contain placeholders only — never a value
that would work if used as-is in production. `.gitignore` excludes every other `.env*` variant explicitly.

## Setup

```bash
# Local backend dev
cp .env.example .env
vim .env   # fill in SECRET_KEY at minimum; everything else has a working dev default

# Production Docker stack
cp docker/.env.example docker/.env
vim docker/.env   # SECRET_KEY, POSTGRES_PASSWORD, NEO4J_PASSWORD, CORS_ORIGINS,
                   # GRAFANA_ADMIN_PASSWORD are required; provider keys are optional

# Validate before deploying
cd apps/api && python scripts/validate_env.py
```

Generate a strong `SECRET_KEY` and database passwords with:

```bash
openssl rand -base64 48
```

There is no RSA keypair anywhere in this codebase's auth flow — `apps/api/src/auth/__init__.py` signs JWTs with
HS256 and a single symmetric `SECRET_KEY`. (An earlier draft of `docs/runbooks/deployment.md` referenced
`JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY`; that was aspirational and has been corrected — don't generate or configure an
RSA keypair for this app.)

## Startup validation

`config.py`'s `Settings` model already fails fast at process start when `APP_ENV=production` and either `SECRET_KEY`
is short/missing or `DATABASE_URL` is still the local-dev default — a misconfigured production deploy won't silently
come up insecure.

For a fuller pre-deploy check (every required/optional variable, without ever printing a secret value), run:

```bash
cd apps/api && python scripts/validate_env.py
```

It exits `0` only when every `REQUIRED_FOR_CORE` variable (see `docs/EXTERNAL_SERVICES_SETUP.md`) is present and not
a known placeholder, and warns (without failing) about missing optional providers, explaining exactly what
functionality degrades without each one. Wire this into a CI/CD pre-deploy gate if you want a hard stop on
misconfiguration.

## Rules

- Never commit a real `.env`, `docker/.env`, or any file containing a live credential. `.gitignore` blocks every
  `.env*` variant except the three tracked `*.example` templates.
- Never put a server-side secret (`ANTHROPIC_API_KEY`, `CHAINALYSIS_API_KEY`, database/Neo4j credentials, etc.) in
  anything that reaches the browser. The only frontend env var that exists is `NEXT_PUBLIC_API_URL`
  (`apps/web/.env.example`) — Next.js inlines `NEXT_PUBLIC_*` vars into the client bundle at build time, so nothing
  with that prefix can ever hold a real secret.
- CI never needs your production secrets: `apps/api/tests` run against ephemeral service containers
  (Postgres/Redis spun up by the workflow) with test-only credentials that exist only for the run.
- If a secret is ever accidentally committed, rotating it is mandatory — removing it from a future commit does not
  invalidate a value that was already pushed to a remote. See "Secret audit" below.

## Secret audit (run 2026-09-03)

Checked: current working tree, all tracked files (`git ls-files`), git history for `.env` (`git log --all -p -- .env`),
and a pattern scan for common credential shapes (`sk-ant-...`, AWS access keys, PEM private key blocks, Slack/GitHub
tokens) across the repository.

**Result: no committed secrets found.** Only `.env.example`, `apps/web/.env.example`, and (as of this pass)
`docker/.env.example` are tracked, and all three contain placeholders only. The dev `docker-compose.yml`'s inline
`SECRET_KEY: dev-secret-key-not-for-production-use-only-min-32-chars` is an intentional, clearly-labeled non-secret
(it's never used by the production compose file, which requires `${SECRET_KEY}` from `docker/.env` with no default).

If this audit is re-run and finds a real credential in history, the required response is: rotate that credential
immediately at the provider (don't just remove it from a future commit — anything ever pushed to a shared remote
must be treated as compromised), then decide separately, with the repo owner's explicit sign-off, whether history
rewriting (`git filter-repo` / BFG) is warranted.
