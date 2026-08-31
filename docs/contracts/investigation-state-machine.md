# Investigation State Machine

> **Status:** Baseline reference (pre-parallel-merge). Derived from `apps/api/src/models/__init__.py::InvestigationStatus`,
> `apps/api/src/services/wallet_analysis.py`, and `apps/api/src/workers/tasks.py::wallet_analysis_task`.
> **Caveat:** WS3 rewires the analysis endpoints to dispatch through Celery (`wallet_analysis_task.delay(...)`) instead of
> running inline. The state transitions below (PENDING → RUNNING → COMPLETED/FAILED) are expected to stay the same either
> way; only the trigger mechanism (sync call vs. `.delay()`) changes. Re-verify once WS3 lands.

## States (`InvestigationStatus` enum)

```
PENDING → RUNNING → COMPLETED
                  └→ FAILED
```

| State | Meaning |
|---|---|
| `PENDING` | Default value on `InvestigationRun` creation (per the SQLAlchemy column default) — in practice, the current code paths (`wallet_analysis_service.analyze_wallet`, `workers/tasks.py::wallet_analysis_task`) both construct the row with `status=RUNNING` directly, so `PENDING` is effectively a theoretical initial state today (never actually persisted as-is by the code paths inspected) unless another code path creates a row without setting status explicitly. |
| `RUNNING` | Investigation is actively being processed (blockchain fetch + Neo4j sync + risk scoring in progress). |
| `COMPLETED` | Finished successfully; `completed_at` set, `result_summary` populated. |
| `FAILED` | Errored; `completed_at` set, `error_message` populated with `str(exception)`. |

## Transition triggers

### 1. Inline path — `src/services/wallet_analysis.py::WalletAnalysisService.analyze_wallet` (current baseline behavior)

Called synchronously from `POST /analysis/cases/{case_id}/wallets/analyze`:

1. Create `InvestigationRun(status=RUNNING, config={trace_depth, max_transactions, started_at})`, flush.
2. Fetch transactions from the chain's `BlockchainProvider`.
3. On success: persist `Transaction` rows, set `status=COMPLETED`, `completed_at=now`, `result_summary={transactions_found, unique_addresses, total_value_eth, chains_analyzed}`.
4. On any exception: set `status=FAILED`, `completed_at=now`, `error_message=str(e)`. **Note:** unlike the Celery task
   version, this path does not re-raise — the caller gets back an `InvestigationRunResponse` with `status: "failed"`
   rather than an HTTP error.

### 2. Celery task path — `src/workers/tasks.py::wallet_analysis_task` (defined, wiring to the API endpoints not yet confirmed in baseline)

Same lifecycle, additionally:
- Also syncs the wallet + transactions into Neo4j (`graph_repository.upsert_wallet` / `upsert_transaction`), runs entity
  enrichment, and runs risk scoring (`risk_scoring_engine.assess_wallet`), updating `Wallet.risk_score` and
  `Wallet.metadata["risk_factors"]` as part of the same transaction.
- On failure: sets `FAILED`, commits, then calls `self.retry(exc=e)` — Celery will retry up to `max_retries=3` with a
  60s default delay before giving up.

### 3. Housekeeping — `src/workers/tasks.py::cleanup_stale_investigations` (periodic task)

Any `InvestigationRun` still `RUNNING` after 24 hours (measured from `started_at`) is force-transitioned to `FAILED`
with `error_message="Investigation timed out (stale for >24 hours)"`. **This is registered as a Celery task but its
periodic trigger (Celery beat schedule) was not found in the baseline tree** — confirm whether `src/workers/main.py`
actually schedules it; if not, note it in `docs/KNOWN_LIMITATIONS.md` as periodic-only/unwired.

## Related: `graph_sync_task` and `entity_enrichment_task`

Both are defined as Celery `shared_task`s in `workers/tasks.py` but, in the baseline tree, no API endpoint or other
code path was found calling `graph_sync_task.delay(...)` or `entity_enrichment_task.delay(...)` directly — the only
enrichment call site found is the synchronous `entity_intelligence.enrich_wallet(...)` call inline inside
`analyze_wallet_in_case` / `wallet_analysis_task` themselves. Treat these two tasks as periodic-only/unwired until
verified otherwise post-merge (WS3 task list explicitly calls this out as something to confirm or document).

## Report generation is a separate, non-versioned lifecycle

`Report` rows have no state machine of their own — they are created once, synchronously, with no draft/pending status.
See `report-schema.md`.
