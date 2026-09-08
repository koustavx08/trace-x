# TRACE-X Investigation Flow

> **Purpose**: End-to-end workflow from suspect wallet address to court-ready investigation report.
> **Status**: Verified against baseline code (commit `9c2b387`, main). Demo mode uses synthetic data; production mode requires Alchemy/Infura API keys.

## Overview

```
Suspect Wallet Address
       ↓
┌─────────────────────────────────────────────────────┐
│  TRACE-X INVESTIGATION WORKFLOW                     │
├─────────────────────────────────────────────────────┤
│  1. ADDRESS VALIDATION                              │
│    • EIP-55 checksum validation                     │
│    • Chain detection (Ethereum/Polygon)            │
│    • Response: {valid, address, chain_id, chain_name}│
│                                                                 │
│  2. WALLET ANALYSIS (CASE CREATION)                 │
│    • POST /analysis/cases/{case_id}/wallets/analyze │
│    • Triggers: wallet_analysis_service.analyze_wallet│
│    • Async: Celery task dispatched (.delay())        │
│    • ↳ Fetch transactions from chain provider       │
│    • ↳ Persist Transaction rows to PostgreSQL        │
│    • ↳ Sync wallet + transactions to Neo4j           │
│    • ↳ Run risk scoring engine (12 factors)         │
│    • ↳ Update Wallet.risk_score & metadata          │
│    • Response: WalletAnalyzeResponse                │
│                                                                 │
│  3. GRAPH TRAVERSAL & PATTERN DETECTION             │
│    • POST /graph/subgraph                           │
│    • POST /graph/wallets/{id}/paths-to-vasp          │
│    • POST /graph/patterns/detect                    │
│      - peel_chain, round_amount, rapid_movement,    │
│        mixer (APOC/Dijkstra algorithms)            │
│    • Response: subgraph nodes/edges, paths, patterns │
│                                                                 │
│  4. VASP ATTRIBUTION                                │
│    • Dijkstra shortest-path to known entities       │
│    • Confidence: Entity_Confidence × Path_Penalty   │
│      × Type_Weight × Value_Factor                   │
│    • Response: AttributionResponse (VASP, confidence  │
│      %, hops, evidence)                             │
│                                                                 │
│  5. RISK ASSESSMENT                                 │
│    • POST /risk/wallets/{wallet_id}/assess          │
│    • 12 weighted risk factors                      │
│    • Severity: CRITICAL≥80, HIGH≥60, MEDIUM≥40,     │
│      LOW≥20, INFO<20                               │
│    • Response: RiskAssessmentResponse              │
│                                                                 │
│  6. AI INVESTIGATION ASSISTANT                      │
│    • POST /ai/query                                  │
│    • 8 query types: RISK_SUMMARY, ATTRIBUTION,      │
│      PATTERN_DETECTION, FUND_FLOW, ENTITY_LOOKUP,   │
│      CASE_OVERVIEW, TIMELINE, COMPARISON            │
│    • Evidence-grounded: constrained to investigation │
│      data + graph intelligence + entity registry     │
│    • Explicit confidence levels; "insufficient      │
│      evidence" guardrails                          │
│    • Response: AIQueryResponse (answer, query_type,   │
│      confidence, evidence[], follow_up_questions[])  │
│                                                                 │
│  7. REPORT GENERATION                               │
│    • POST /risk/reports/generate                    │
│    • Templates: Executive Summary, Technical        │
│      Findings, Evidence Package, Legal Brief        │
│    • Formats: PDF (%PDF- magic bytes), HTML, JSON   │
│    • Response: ReportGenerateResponse (report_id,     │
│      title, format, file_size, generated_at)         │
│                                                                 │
│  8. FRONTEND DISPLAY                                │
│    • Dashboard: cases, wallets, investigations      │
│    • Graph: React Flow with real Neo4j data         │
│    • Risk: Factor breakdown table                   │
│    • AI: Chat interface with session persistence     │
│    • Reports: Downloadable PDF/HTML/JSON            │
└─────────────────────────────────────────────────────┘
       ↓
Investigation Report + Graph + Evidence Package
```

## Flow Details

### 1. Address Validation

| Step | API | Request | Response |
|------|-----|---------|----------|
| Validate | `POST /analysis/wallets/validate` | `{address, chain_id?}` | `{valid, address, chain_id, chain_name, ...}` |

**Validation**: EIP-55 checksum + eth-utils `is_valid_address`. Returns `valid: false` for invalid addresses; never crashes.

### 2. Wallet Analysis

| Step | API | Request | Response |
|------|-----|---------|----------|
| Analyze | `POST /analysis/cases/{case_id}/wallets/analyze` | `WalletAnalyzeRequest{address, chain_id?, label?, trace_depth, max_transactions}` | `WalletAnalyzeResponse{wallet, investigation}` |

**Inline path** (baseline): Synchronous execution from `POST /analysis/cases/{case_id}/wallets/analyze` → `wallet_analysis_service.analyze_wallet` → investigation run with status `RUNNING` → fetch transactions → persist → risk scoring → COMPLETED/FAILED.

**Celery path** (WS3): Same lifecycle but `.delay()` dispatched from the API endpoint; worker processes the task asynchronously with retry (max_retries=3, 60s default delay).

### 3. Graph Traversal & Pattern Detection

| Endpoint | Purpose | Algorithm |
|----------|---------|-----------|
| `POST /graph/subgraph` | Extract subgraph for wallet addresses | Neo4j MATCH patterns |
| `POST /graph/wallets/{id}/paths-to-vasp` | Shortest paths to exchange/bridge entities | Dijkstra (APOC) |
| `POST /graph/patterns/detect` | Pattern detection (peel chain, round amounts, etc.) | Custom Cypher + APOC |

**Pattern types**: `peel_chain`, `round_amount`, `rapid_movement`, `mixer`.

### 4. VASP Attribution

| Step | Description |
|------|-------------|
| Shortest path | Dijkstra from suspect wallet to known VASP nodes in entity registry |
| Confidence formula | `Entity_Confidence × Path_Penalty × Type_Weight × Value_Factor` |
| Attribution types | `DIRECT`, `INDIRECT`, `CLUSTER`, `HEURISTIC` |
| Output | VASP name, confidence % (e.g. `94.2%`), hops count, value, evidence list |

### 5. Risk Assessment

| Factor | Weight | Trigger |
|--------|--------|---------|
| Mixer Interaction | 0.25 | `graph_context["mixer_interactions"]` non-empty |
| Peel Chain | 0.20 | entries where `origin == wallet.address.lower()` |
| Round Amounts | 0.08 | ≥3 transactions with whole-ETH values |
| Rapid Movement | 0.10 | ≥3 tx pairs <300s apart |
| High-Risk Entity | 0.15 | entity_type in {MIXER, SANCTIONED, DARKNET, GAMBLING} |
| Sanctions Hit | 0.30 | entity_type == SANCTIONED |
| Large Value Transfer | 0.07 | any tx ≥100 ETH |
| Cross-Chain Bridge | 0.05 | bridge-token symbol + method contains "bridge" |
| Contract Interaction | 0.05 | >10 non-"transfer" transactions |
| New Wallet | 0.03 | tx_count < 5 ∧ age <30 days |
| Low Liquidity Token | 0.02 | illiquid token interactions |
| Dusting Attack | 0.02 | micro-transfer patterns |

**Overall score**: `min(base_score × 1.1, max_possible, 100.0)` where `base_score = Σ(weighted_score) / Σ(weight)` and `max_possible = max(factor.score)`.

**Severity thresholds**: CRITICAL≥80, HIGH≥60, MEDIUM≥40, LOW≥20, INFO<20.

### 6. AI Investigation Assistant

| Query Type | Example | Response Includes |
|------------|---------|-------------------|
| Risk Summary | "Risk for wallet 0x742d..." | Score, factors, evidence, follow-ups |
| Attribution | "Where did funds from 0x... go?" | VASP, path, confidence, evidence |
| Patterns | "Suspicious patterns on Ethereum?" | Peel chains, round amounts, mixers |
| Fund Flow | "Trace money from 0x..." | Path, hops, value, VASP endpoint |
| Entity Lookup | "Who owns 0x...?" | Entity, type, confidence, source |
| Case Overview | "Case TRX-20240115-0042" | Stats, wallets, investigations |
| Timeline | "Timeline for wallet 0x..." | Daily volume, peak activity |
| Comparison | "Compare wallet A vs B" | Side-by-side risk/attribution |

**Guardrails**:
- Never queries blockchain directly
- Constrained to investigation evidence
- Explicit confidence levels
- "Insufficient evidence" vs. speculation
- Follow-up questions based on available data

### 7. Report Generation

| Template | Use Case | Formats |
|----------|----------|---------|
| Executive Summary | Leadership briefing | PDF, HTML |
| Technical Findings | Analyst deep-dive | PDF, JSON |
| Evidence Package | Prosecution/court | PDF, JSON |
| Legal Brief | Legal team | PDF, HTML |

**Every report includes**:
- Methodology & limitations section
- Hash-linked evidence appendix
- Confidence levels for every attribution
- Methodology disclosure for legal defensibility

## Demo vs Production Flow Differences

| Step | Demo Mode | Production Mode |
|------|-----------|-----------------|
| 1. Address validation | Pre-validated synthetic address | Real EIP-55 validation |
| 2. Wallet analysis | Pre-computed synthetic results | Live chain fetch via Alchemy/Infura |
| 3. Graph traversal | Pre-computed graph data | Real Neo4j queries |
| 4. VASP attribution | Pre-seeded (e.g. Binance CONFIRMED) | Live graph traversal + entity registry |
| 5. Risk assessment | Fixed 91.2 CRITICAL score | 12-factor weighted scoring |
| 6. AI assistant | Structured template responses | Live LLM calls (fallback to demo mode) |
| 7. Report generation | HTML/JSON placeholder | PDF (%PDF- magic bytes) + HTML + JSON |

## Environment Requirements

**Minimum for demo** (`.env`):
```
APP_ENV=development
SECRET_KEY=your-secret-key-min-32-chars
DATABASE_URL=postgresql+asyncpg://tracex:tracex@localhost:5432/tracex
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=tracexneo4j
REDIS_URL=redis://localhost:6379/0
```

**For live analysis** (add to above):
```
ALCHEMY_API_KEY=your-key
INFURA_API_KEY=your-key
```

**AI mode**: `AI_MODE=demo` (default when no key set) → deterministic templates; `AI_MODE=live` with `ANTHROPIC_API_KEY` → real Claude calls.

## Verification

The investigation workflow has been verified end-to-end through the CI test suite (`apps/api/tests/`) with the following coverage:

- `test_health.py` - Health endpoint verification
- `test_auth.py` - Auth flow (login/refresh/logout, RBAC, audit logging)
- `test_wallets.py` - Wallet CRUD and validation
- `test_cases.py` - Case management
- `test_graph.py` - Graph sync and query endpoints
- `test_risk.py` - Risk assessment and attribution endpoints
- `test_ai.py` - AI query classification and chat session persistence
- `test_reports.py` - PDF/HTML/JSON report generation
- `test_providers.py` - Provider registry and EVM transaction parsing

All 171 backend tests pass with 0 failures (CI run `33515624922`, commit `9c2b387`).

## Known Limitations (Flow-Specific)

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| No live blockchain data without API keys | Analysis uses synthetic/pre-computed results | Demo mode provides full workflow demonstration |
| Graph data is Neo4j-dependent | Graph page shows placeholder without Neo4j | Judge Mode (`/demo`) has pre-computed graph data |
| AI responses are template-based (no LLM) | May not answer novel queries | Evidence-grounded constraints; "insufficient evidence" fallback |
| Report PDF generation is stubbed | Download returns placeholder | HTML/JSON formats work fully |
| Celery beat not wired for housekeeping | Stale investigations not auto-finalized | Manual status update via API `PATCH /investigations/{id}` |
| Only Ethereum + Polygon providers registered | BSC/other chains unavailable | BSC RPC URL configurable via `BSC_RPC_URL` env var |

---
*TRACE-X Investigation Flow — verified against commit `9c2b387` on `main`*