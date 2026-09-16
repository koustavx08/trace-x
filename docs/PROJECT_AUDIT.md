# TRACE-X Project Audit: Bugs, Gaps & Fraudster Evasion Vectors

> **Audit Date**: 2026-09-16  
> **Scope**: Full codebase — backend engines, graph layer, auth, frontend, infra  

---

## Part 1: Bugs & Code Issues That Need Fixing

### 🔴 CRITICAL

#### 1. API Keys Committed to Source Control
- **File**: [`.env`](file:///home/babu/SIH/trace-x/.env)
- **Issue**: `OPENROUTER_API_KEY`, `ALCHEMY_API_KEY`, and `SECRET_KEY` are hardcoded in the `.env` file committed to git. Anyone with repo access can impersonate the system, call OpenRouter on your bill, or forge admin JWTs.
- **Fix**: Add `.env` to `.gitignore`, rotate all keys immediately, use `.env.example` with placeholders only.

#### 2. SECRET_KEY Is a Known Placeholder
- **File**: [`.env`](file:///home/babu/SIH/trace-x/.env) line 1
- **Value**: `trace-x-super-secret-key-change-in-production`
- **Impact**: This exact string is in `_PLACEHOLDER_SECRET_KEYS` in [`config.py`](file:///home/babu/SIH/trace-x/apps/api/src/core/config.py#L35-L42), meaning the validation only blocks it in `APP_ENV=production`. In development/demo, **anyone can mint admin JWTs** by signing with this publicly known key.
- **Fix**: Generate a proper random key: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

#### 3. `/forensics` Page Is a Dead Link (404)
- **File**: [`layout.tsx`](file:///home/babu/SIH/trace-x/apps/web/src/app/%28dashboard%29/layout.tsx#L35) registers the route
- **Issue**: The sidebar links to `/forensics` but **no `page.tsx` exists** at `apps/web/src/app/(dashboard)/forensics/`. Users clicking "Forensics" get a 404. The backend API at [`/api/v1/forensics`](file:///home/babu/SIH/trace-x/apps/api/src/api/v1/forensics.py) exists and works, but there's no UI to consume it.
- **Fix**: Create `apps/web/src/app/(dashboard)/forensics/page.tsx`.

---

### 🟠 HIGH

#### 4. `datetime.utcnow()` Is Deprecated (Python 3.12+)
- **Files**: [`auth/__init__.py`](file:///home/babu/SIH/trace-x/apps/api/src/auth/__init__.py) (lines 411, 413, 426, 428, 581), [`risk_engine.py`](file:///home/babu/SIH/trace-x/apps/api/src/analytics/risk_engine.py#L72)
- **Issue**: `datetime.utcnow()` was deprecated in Python 3.12. It returns a naive datetime that loses timezone info, causing comparison bugs when mixed with aware datetimes (already patched in `blacklist_token` at line 88-89, proving the problem exists).
- **Fix**: Replace all with `datetime.now(UTC)`.

#### 5. CORS Allows `*` Methods and `*` Headers
- **File**: [`config.py`](file:///home/babu/SIH/trace-x/apps/api/src/core/config.py#L87-L88)
- **Issue**: `CORS_ALLOW_METHODS: ["*"]` and `CORS_ALLOW_HEADERS: ["*"]` in development defaults. If deployed without overriding, this allows any origin to call `DELETE`, `PATCH`, etc.
- **Fix**: Restrict to `["GET", "POST", "PUT", "DELETE", "OPTIONS"]` and specific headers like `["Authorization", "Content-Type"]`.

#### 6. Neo4j Password Hardcoded in Default Config
- **File**: [`config.py`](file:///home/babu/SIH/trace-x/apps/api/src/core/config.py#L79)
- **Issue**: `NEO4J_PASSWORD: str = "tracexneo4j"` is a hardcoded default. The production validator only checks `SECRET_KEY` and `DATABASE_URL` — Neo4j credentials pass unchecked.
- **Fix**: Add Neo4j password validation to `_validate_production_requirements`.

#### 7. Mixer Pattern Detection Passes Empty Address
- **File**: [`graph.py`](file:///home/babu/SIH/trace-x/apps/api/src/api/v1/graph.py#L154-L158)
- **Code**: `find_mixer_interactions(address="", chain=request.chain, max_hops=4)` — the `"mixer"` pattern type sends an empty string as the address, which is meaningless.
- **Fix**: For global mixer detection, use a different query that doesn't require a starting address.

#### 8. `GraphTransaction.value` Type Mismatch
- **File**: [`models/__init__.py`](file:///home/babu/SIH/trace-x/apps/api/src/graph/models/__init__.py#L75)
- **Issue**: `value: str` but many callers pass `float` (e.g., the seed scripts pass `value_usd` as float). The Neo4j driver accepts it, but it means edge weights for Dijkstra are stored as strings and `toFloat()` coercion is needed in every Cypher query.
- **Fix**: Change to `value: float` and update all callers.

---

### 🟡 MEDIUM

#### 9. No Pagination on Graph Queries
- **Issue**: `get_subgraph`, `find_paths_to_entities`, and `detect_clusters` return unbounded result sets. A dense graph can return thousands of nodes and crash the browser.
- **Fix**: Add `LIMIT` parameters and server-side pagination.

#### 10. Audit Logger Silently Drops Entries on Redis Failure
- **File**: [`auth/__init__.py`](file:///home/babu/SIH/trace-x/apps/api/src/auth/__init__.py#L111-L112)
- **Issue**: `is_token_blacklisted` returns `False` when Redis is down (fail-open), meaning a revoked token is accepted. The comment says "log and allow" — this is a security trade-off that should at minimum be configurable.

#### 11. No Input Sanitization on Cypher Parameters
- **Issue**: While Neo4j parameterized queries prevent injection, the string interpolation in `entity_filter` at [`repository.py`](file:///home/babu/SIH/trace-x/apps/api/src/graph/repository.py#L311-L315) uses f-string formatting with `quoted_types` directly interpolated into the Cypher query. This is safe only because it comes from an enum, but it's fragile.

#### 12. Search Bar in Dashboard Is Non-Functional
- **File**: [`layout.tsx`](file:///home/babu/SIH/trace-x/apps/web/src/app/%28dashboard%29/layout.tsx#L306-L316)
- **Issue**: The search input has no `onChange`, no API call, no state — it's purely cosmetic.

---

## Part 2: Missing Features & Incomplete Implementations

| Feature | Status | Impact |
|---|---|---|
| **`/forensics` UI page** | ❌ Route registered, no page.tsx | Users can't visualize taint/motif/flow results |
| **Real-time Mempool Alerting** | ❌ Not started | No live alerts when suspect wallets move funds |
| **Legal Notice Generator UI** | ❌ Backend exists, no UI modal | Must use API directly to generate Section 91 notices |
| **Cross-Chain Bridge Event Matcher** | ⚠️ Engine exists, no live data feed | Only works on demo data, can't match real bridge events |
| **T-GNN / EvolveGCN** | ❌ Specified in docs, not implemented | No ML-based anomaly detection for zero-day patterns |
| **P2P / OTC Fiat Correlation** | ⚠️ Engine exists, no 1930 Portal integration | Can't match UPI/IMPS timestamps to on-chain releases |
| **Global search** | ❌ UI element exists, no functionality | Can't search by tx hash, address, or case number |
| **Notification system** | ❌ Bell icon exists, no backend | No alerting infrastructure at all |
| **Multi-factor authentication** | ❌ Not implemented | Single-factor JWT only |

---

## Part 3: How a Fraudster Can Escape Detection (Evasion Vectors)

> [!CAUTION]
> This section documents the weaknesses a sophisticated adversary would exploit against the **current** TRACE-X implementation. Each vector maps to a gap in the deployed algorithms.

---

### Evasion 1: **Timing Randomization** (Defeats Motif Engine)

**How the system works**: The VF2 motif engine enforces `Δt ≤ T_max` (default 30 min) between consecutive transactions in a pattern.

**How a fraudster escapes**:
- Introduce **random delays of 45-120 minutes** between each hop
- The fan-out or peel chain still exists structurally, but the temporal window constraint rejects it
- The motif engine returns **zero matches** even though the structure is obvious

**Current gap**: The default `T_max` is hardcoded. There's no adaptive windowing or escalating scan (try 30 min, then 60, then 120, etc.).

---

### Evasion 2: **Dust Contamination** (Defeats Taint Engine — Haircut Model)

**How the system works**: Haircut taint computes `taint_ratio = tainted_balance / total_balance`.

**How a fraudster escapes**:
- Before moving stolen funds, deposit **$10M of clean funds** into the same wallet
- The taint ratio drops from 100% to `$50k / $10.05M = 0.5%`
- At 0.5% taint, the wallet falls below any reasonable `min_taint_usd` threshold when forwarding
- The taint engine reports **"clean"** even though $50k of stolen money passed through

**Current gap**: The FIFO model handles this better (the clean funds arrived *after* the stolen ones), but the API returns haircut results by default. There's no alert when haircut and FIFO results **diverge dramatically** — which is itself the strongest signal.

---

### Evasion 3: **DEX Swaps** (Invisible to Current Providers)

**How the system works**: The providers track `transfer` events and direct ETH/USDT movements.

**How a fraudster escapes**:
- Swap ETH → obscure ERC-20 token on Uniswap → transfer token → swap back to ETH on another DEX
- The current EVM provider tracks `Transfer(address,address,uint256)` events but **does not decode Uniswap `Swap` events**
- The trace breaks: the system sees ETH leaving wallet A to the Uniswap router, then nothing

**Current gap**: No DEX event log decoder. The `method` field in `GraphTransaction` stores `"transfer"` or `"lock"` but not `"swap"`, `"exactInputSingle"`, etc.

---

### Evasion 4: **Privacy Coins / Tornado Cash Note Reuse** (Defeats Graph Traversal)

**How the system works**: Dijkstra and taint propagation follow `SENT → Transaction → RECEIVED` paths.

**How a fraudster escapes**:
- Deposit into Tornado Cash with a secret note → wait 6 months → withdraw from a fresh wallet
- There is **no on-chain link** between the deposit tx and the withdrawal tx
- The current system models the mixer as a single node and applies pro-rata taint, but **only if it already knows both the deposit AND withdrawal wallets belong to the same case**
- A truly unknown withdrawal wallet is never discovered

**Current gap**: No Tornado Cash note correlator. The system cannot discover withdrawal addresses unless they're already in the graph.

---

### Evasion 5: **Gas-Price Manipulation** (Defeats Clustering)

**How the system works**: The clustering engine groups wallets by "gas-payer" heuristic — if 50 wallets receive initial gas from the same parent within 1 hour, they're clustered.

**How a fraudster escapes**:
- Fund each burner wallet's gas from a **different gas-funding address** (use a cascade: funder A → funder B → burner 1, funder C → funder D → burner 2)
- Or use **Flashbots private transactions** to fund gas — these don't appear in the public mempool/block until mined, and the gas-payer analysis window might miss them
- The clustering engine sees 50 independent wallets with no common parent

**Current gap**: The gas-payer heuristic only goes 1 hop deep. A 2-hop cascade defeats it.

---

### Evasion 6: **Cross-Chain via Unmonitored Bridges** (Defeats Bridge Matcher)

**How the system works**: The bridge matcher correlates `Lock` on Chain A with `Mint` on Chain B by value and timing.

**How a fraudster escapes**:
- Use bridges to chains TRACE-X doesn't support: **Solana, Cosmos, Avalanche, zkSync Era, Polygon zkEVM**
- The system currently supports only Ethereum, Tron, and Bitcoin
- Even within supported chains, use **bridges the matcher doesn't know about** (there are 100+ bridges; the system only matches value/timing, not specific bridge contract addresses)

**Current gap**: Only 3 chains supported. No bridge contract registry. The matcher is timing-based and can be spoofed by multiple same-value transfers.

---

### Evasion 7: **Peel Chain with Round-Trip Decoys** (Defeats Flow-Weighted Dijkstra)

**How the system works**: Dijkstra follows the **highest-value edges** (inverse log weight), so the main money corridor is the "shortest" path.

**How a fraudster escapes**:
- Send the real stolen funds via small, randomized amounts ($3,271, $4,892, $2,103)
- Simultaneously run **high-value decoy transfers** ($500k) between wallets you control that go nowhere
- Dijkstra's inverse-log weight makes the $500k decoy path the "shortest" and reports it as the primary corridor
- The investigator chases the decoy while the real money exits through the low-value paths

**Current gap**: No heuristic to distinguish a high-value dead-end from a genuine laundering corridor. Max-flow helps here but isn't the default view.

---

### Evasion 8: **Nested Smart Contracts** (Defeats Direct Tracing)

**How a fraudster escapes**:
- Deploy a custom smart contract that receives ETH, holds it in internal storage, then releases it via `selfdestruct` or `CREATE2` to a new address
- Internal contract calls don't emit `Transfer` events unless explicitly coded to
- The provider's log-based approach misses the movement entirely

**Current gap**: No `trace_transaction` / `debug_traceCall` integration to capture internal calls.

---

### Evasion 9: **Sybil Attack on Entity Attribution**

**How a fraudster escapes**:
- Create a wallet that interacts heavily with Binance (real deposits/withdrawals) to build a "confirmed exchange" profile
- Then use that wallet as a pass-through for stolen funds
- TRACE-X's entity attribution marks it as "Binance" with `CONFIRMED` confidence, and an investigator might assume it's Binance's hot wallet rather than a criminal's personal account

**Current gap**: Entity attribution trusts interaction patterns. There's no verification that a wallet is **owned by** the entity vs. merely **interacts with** the entity.

---

## Part 4: Priority Fix Ranking

| Priority | Item | Effort | Impact |
|---|---|---|---|
| **P0** | Rotate leaked API keys, add `.env` to `.gitignore` | 10 min | Security breach prevention |
| **P0** | Generate real `SECRET_KEY` | 5 min | Prevents JWT forgery |
| **P1** | Build `/forensics` UI page | 1-2 days | Users can't access core feature |
| **P1** | Add haircut-vs-FIFO divergence alert | 4 hours | Catches dust contamination evasion |
| **P1** | Fix empty address in mixer detection | 30 min | Mixer pattern detection is broken |
| **P2** | Replace `datetime.utcnow()` | 1 hour | Python 3.12+ deprecation |
| **P2** | Add DEX swap event decoder | 2-3 days | Major evasion vector |
| **P2** | Multi-hop gas-payer clustering | 1 day | Defeats cascade gas funding |
| **P3** | Global search functionality | 2 days | UX improvement |
| **P3** | Notification/alerting backend | 3-5 days | No real-time alerts |
| **P3** | Additional chain support (Solana, etc.) | 1-2 weeks per chain | Cross-chain evasion |
