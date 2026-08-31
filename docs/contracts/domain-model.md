# TRACE-X Domain Model

> **Status:** Baseline reference (pre-parallel-merge). Derived from `apps/api/src/models/__init__.py` (SQLAlchemy ORM,
> Postgres) and `apps/api/src/schemas/__init__.py` (Pydantic API schemas). WS1 appends an `AuditLog` model — not shown
> here since it did not exist in the baseline tree; check `apps/api/src/models/__init__.py` post-merge.

## Entity-relationship overview

```
User (1) ──< assigned_cases >── Case (N)
Case (1) ──< wallets >──────────── Wallet (N)
Case (1) ──< investigation_runs >── InvestigationRun (N)
Case (1) ──< reports >──────────── Report (N)
Wallet (1) ──< transactions >───── Transaction (N)
Wallet (1) ──< investigation_runs >── InvestigationRun (N)
InvestigationRun (1) ──< reports (optional) >── Report (N)
```

All primary keys are `UUID` (Postgres `uuid` type), generated client-side via `uuid.uuid4()` as the SQLAlchemy column
default (not `gen_random_uuid()` / a DB-side default) — this is why no `pgcrypto`/`uuid-ossp` Postgres extension is
required at provisioning time (see `docker/docker-compose.prod.yml`, which mounts no init script and relies solely on
Alembic for schema).

## Enums (mirrored identically between `models/__init__.py` and `schemas/__init__.py`)

| Enum | Values |
|---|---|
| `CaseStatus` | `open`, `in_progress`, `closed`, `archived` |
| `CrimeType` | `fraud`, `money_laundering`, `ransomware`, `darknet_market`, `sanctions_evasion`, `other` |
| `UserRole` | `analyst`, `supervisor`, `admin` |
| `AttributionStatus` | `unverified`, `under_review`, `attributed`, `confirmed` |
| `InvestigationStatus` | `pending`, `running`, `completed`, `failed` (see `investigation-state-machine.md`) |
| `ConfidenceLevel` (schemas only) | `CONFIRMED`, `HIGH_CONFIDENCE`, `PROBABLE`, `UNKNOWN` |

## `User` (`users`)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| email | string(255) | unique, indexed |
| full_name | string(255) | |
| hashed_password | string(255) | bcrypt via `passlib` |
| role | `UserRole` | default `analyst` |
| is_active | bool | default `true` |
| last_login_at | datetime? | |
| created_at / updated_at | datetime | server defaults |

Relationship: `assigned_cases` — cases where `Case.assigned_to == User.id`.

## `Case` (`cases`)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| case_number | string(50) | unique, indexed (e.g. `TRX-YYYYMMDD-NNNN` per docs elsewhere) |
| title | string(255) | |
| crime_type | `CrimeType` | default `fraud` |
| description | text | |
| status | `CaseStatus` | default `open` |
| assigned_to | UUID? FK → users.id | |
| case_metadata | JSON? | exposed to the API as `metadata` (Pydantic schema aliasing) |
| created_at / updated_at | datetime | |

Indexes: `(status, created_at)`, `(assigned_to, status)`.
Relationships: `assignee`, `wallets` (cascade delete-orphan), `investigation_runs` (cascade), `reports` (cascade).

## `Wallet` (`wallets`)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| case_id | UUID FK → cases.id (CASCADE delete) | |
| address | string(66) | indexed |
| chain | string(50) | indexed (e.g. `"Ethereum"`, `"Polygon"` — human-readable name, not chain id) |
| label | string(100)? | |
| attribution_status | `AttributionStatus` | default `unverified` |
| risk_score | Numeric(5,2) | default `0.0`, 0–100 |
| entity_name | string(255)? | |
| entity_confidence | string(20)? | stores a `ConfidenceLevel` value as free text |
| first_seen_tx_hash | string(66)? | |
| wallet_metadata | JSON? | exposed as `metadata` |
| created_at / updated_at | datetime | |

Indexes: `(case_id, chain)`; unique `(address, chain)`.
Relationships: `case`, `transactions` (cascade), `investigation_runs` (cascade).

**Note:** the ORM model has no `entity_type` column, but `src/api/v1/graph.py` reads `wallet.entity_type` when building
`GraphEntity` / `GraphWallet` objects. This looks like a latent bug (would raise `AttributeError` at runtime) — worth a
fixup pass once the owning workstream (WS3, providers/graph wiring) lands; flagged in `docs/KNOWN_LIMITATIONS.md`.

## `Transaction` (`transactions`)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| wallet_id | UUID FK → wallets.id (CASCADE) | |
| tx_hash | string(66) | unique index |
| block_number | int | |
| timestamp | datetime (tz-aware) | indexed |
| from_address / to_address | string(66) | both indexed |
| value | string(78) | wei, stored as string to avoid precision loss on 256-bit integers |
| value_usd | Numeric(18,2)? | |
| token_address / token_symbol | string?, string(20)? | ERC-20 transfer fields |
| method | string(100)? | decoded contract method name |
| is_suspicious | bool | default `false` |
| transaction_metadata | JSON? | exposed as `metadata` |
| created_at | datetime | |

Indexes: `(wallet_id, timestamp)`, unique `tx_hash`, `(from_address, to_address)`.

## `InvestigationRun` (`investigation_runs`)

See `investigation-state-machine.md` for the full lifecycle. Columns: `id`, `case_id` (FK, CASCADE), `wallet_id` (FK,
CASCADE), `status` (`InvestigationStatus`), `started_at`, `completed_at?`, `error_message?` (text), `config?` (JSON —
e.g. `{trace_depth, max_transactions}`), `result_summary?` (JSON — e.g. `{transactions_found, risk_assessment, ...}`),
`created_at`/`updated_at`.

## `Report` (`reports`)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| case_id | UUID FK → cases.id (CASCADE) | |
| investigation_run_id | UUID? FK → investigation_runs.id | |
| title | string(255) | |
| summary | text | |
| findings | JSON (not null) | |
| risk_assessment | JSON (not null) | |
| graph_snapshot | JSON? | |
| generated_by | UUID FK → users.id | |
| format | string(10) | default `"json"`; API-layer validates `^(pdf|json|html)$` |
| file_path | string(500)? | |
| created_at / updated_at | datetime | |

See `report-schema.md` for the generation pipeline and its current gaps.

## Migrations

`apps/api/alembic/versions/`: `001_initial.py` (base schema), `002_add_hashed_password.py`. Alembic is the sole owner
of schema management — see the note above re: no Postgres init-script mount being needed.
