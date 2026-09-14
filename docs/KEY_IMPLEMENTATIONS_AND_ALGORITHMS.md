# TRACE-X: Master Blueprint — Key Implementations, Forensic Algorithms & Strategic Roadmap

> **Document Version:** 2.0.0  
> **Target Audience:** Core Engineering Team, Forensics Analysts, SIH 2026 Evaluation Panel, Law Enforcement Tech Units  
> **Status:** Comprehensive Engineering Specification & Architecture Blueprint  

---

## 1. Executive Summary

TRACE-X currently provides a dual-engine architecture combining **Dijkstra's Shortest Path Algorithm on Neo4j** with a deterministic **12-factor risk scoring engine** and an **evidence-grounded AI Co-pilot**. 

While this architecture successfully attributes linear multi-hop fund movements, modern cybercriminals, money-laundering cartels, and scam syndicates frequently employ **non-linear, multi-branching, multi-chain, and temporal evasion techniques** (e.g., smurfing/fan-out, peel chains, automated mixers, DEX swaps, P2P off-ramps, and bridge hops).

This document provides a comprehensive, exhaustive specification of all **forensic algorithms, multi-chain providers, legal compliance modules, and operational enhancements** required to build a production-grade, courtroom-admissible cryptocurrency forensics platform.

---

## 2. Core Forensic Algorithms to Implement

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                  TRACE-X FORENSIC ALGORITHM SUITE                                │
├──────────────────────────┬──────────────────────────┬────────────────────────────────────────────┤
│ 1. Graph & Flow Layer    │ 2. Entity Resolution     │ 3. Pattern & AI Layer                      │
├──────────────────────────┼──────────────────────────┼────────────────────────────────────────────┤
│ • Flow-Weighted Dijkstra │ • Union-Find Clustering  │ • Temporal Motif Mining (VF2 Isomorphism)  │
│ • Taint Propagation      │ • Co-spending Heuristic  │ • Temporal Graph Neural Networks (T-GNNs)  │
│   (Haircut / FIFO)       │ • Gas-Payer Grouping     │ • Cross-Chain Bridge Event Matcher         │
│ • Max-Flow / Min-Cut     │ • Louvain Community      │ • P2P / OTC Escrow Correlation Matcher     │
└──────────────────────────┴──────────────────────────┴────────────────────────────────────────────┘
```

---

### 2.1. Taint Analysis & Flow Propagation Engine

#### The Problem with Simple Dijkstra:
Standard shortest-path algorithms evaluate binary connectivity ($A \rightarrow B$). When a criminal mixes \$100,000 of stolen funds with \$100,000 of clean liquidity in an intermediary wallet and forwards \$50,000 to an exchange, Dijkstra cannot calculate the concentration of tainted funds that reached the destination.

#### Algorithm Specification:
TRACE-X implements two complementary taint propagation models in `apps/api/src/analytics/taint_engine.py`:

```
                    ┌──> Transfer 1 ($30,000) ──> Taint: 75% ($22,500 illicit)
                    │
[Wallet A] ─────────┼──> Transfer 2 ($50,000) ──> Taint: 75% ($37,500 illicit)
Balance: $100,000   │
Illicit: $75,000    └──> Transfer 3 ($20,000) ──> Taint: 75% ($15,000 illicit)
(Taint: 75%)
```

1. **Pro-Rata ("Haircut") Model**:
   $$\text{Taint}_{\text{out}} = \text{Taint}_{\text{wallet}} \times \frac{\text{Amount}_{\text{transfer}}}{\text{Total Balance}_{\text{wallet}}}$$
   * Every outgoing payment from an address receives an equal percentage of the wallet's current taint index.
2. **FIFO (First-In, First-Out) Poison Model**:
   * Tracks discrete value units chronologically. Outgoing transactions are tainted in the order in which tainted funds were deposited until the illicit amount is exhausted.

#### Implementation Target:
* **File**: `apps/api/src/analytics/taint_engine.py`
* **Output**: Exact quantitative dollar amount (\$ USD) and taint percentage ($0-100\%$) reaching each destination exchange deposit wallet for precise asset recovery claims.

---

### 2.2. Flow-Weighted Shortest Path & Maximum Flow

#### The Problem:
Current Dijkstra uses a uniform relationship weight (`1.0`), meaning it optimizes purely for the fewest wallet hops. A 1-hop \$10 decoy transfer can take priority over a 2-hop \$1,000,000 main laundering pipeline.

#### Algorithm Specification:
1. **Inverse Logarithmic Edge Weighting**:
   Replace static weights in Neo4j APOC Dijkstra with dynamic transaction value weights:
   $$W(e) = \frac{1}{\log_{10}(\text{Value}_{\text{USD}}(e) + 1)}$$
   * High-value transactions yield very small edge weights, causing Dijkstra to naturally traverse the primary money corridor.
2. **Max-Flow / Min-Cut (Edmonds-Karp / Push-Relabel)**:
   * Models the wallet graph as a flow network $G = (V, E)$ where edge capacity $c(u, v)$ is the total transferred volume.
   * Calculates the maximum illicit flow capacity between source suspect wallets and target exchange sinks.

#### Implementation Target:
* **File**: [apps/api/src/graph/repository.py](file:///home/babu/SIH/trace-x/apps/api/src/graph/repository.py) & [apps/api/src/graph/queries.py](file:///home/babu/SIH/trace-x/apps/api/src/graph/queries.py)

---

### 2.3. Entity Resolution & Wallet Clustering (Union-Find)

#### The Problem:
Criminal syndicates deploy automated scripts creating 500–1,000 disposable intermediate burner wallets. Searching raw wallet-to-wallet graphs results in combinatorial explosion and unreadable visual sprawl.

#### Algorithm Specification:
Implements **Disjoint-Set (Union-Find)** with path compression and union by rank:

1. **Multi-Input Co-Spending Heuristic (UTXO / Account)**:
   * If Address $A$ and Address $B$ both sign as inputs to the same transaction, merge their sets: $\text{Union}(A, B)$.
2. **Gas-Payer Attribution Heuristic**:
   * If 50 newly created burner addresses receive their initial gas funding from the same parent address within a 1-hour window, cluster them under the parent entity:
     $$\forall w \in W, \quad \text{Parent}(w) = \text{GasFunder}$$
3. **Change Address Detection**:
   * Identifies one-time change addresses using standard script heuristics and address reuse patterns.

#### Implementation Target:
* **File**: `apps/api/src/analytics/clustering_engine.py`
* **Outcome**: Collapses 1,000+ burner addresses into 2–3 logical "Actor Super-Nodes", reducing graph search latency by over 80%.

---

### 2.4. Temporal Subgraph & Motif Matching (VF2 Isomorphism)

#### The Problem:
Money laundering operations exhibit structured geometric signatures that cannot be discovered by simple path queries.

#### Key Motifs Detected:
```
1. Smurfing / Layering (Fan-Out -> Fan-In):
   [Source] ──┬──> [Mule 1] ──┐
              ├──> [Mule 2] ──┼──> [Exchange Deposit]
              └──> [Mule 3] ──┘

2. Peel Chain:
   [Source] ──> [Hop 1] ──> [Hop 2] ──> [Hop 3]
                  │           │           │
                  └──> [VASP] └──> [VASP] └──> [VASP]

3. U-Turn / Cyclical Wash:
   [Wallet A] ──> [Wallet B] ──> [Wallet C] ──> [Wallet A]
```

#### Algorithm Specification:
* **VF2 Subgraph Isomorphism Algorithm** operating with temporal window constraints:
  $$\Delta t = t(\text{tx}_{i+1}) - t(\text{tx}_i) \le T_{\text{max}} \quad (\text{e.g., } 30\text{ minutes})$$
* Matches subgraphs matching predefined laundering templates in polynomial time.

---

### 2.5. Temporal Graph Neural Networks (T-GNNs / EvolveGCN)

#### The Problem:
Static rules cannot detect zero-day evasion techniques, dynamic timing randomization, or previously unseen laundering behaviors.

#### Architecture:
* **EvolveGCN / T-GCN (Temporal Graph Convolutional Network)**:
  * **Static & Dynamic Node Features**: In/Out degree, transaction frequency, gas price spikes, balance entropy, wallet age, token velocity.
  * **Temporal Recurrent Aggregator**: Captures how topological relationships evolve over discrete block time slices.
* **Output Predictions**:
  * Predicts wallet roles with probabilistic confidence: `Mule Wallet (92%)`, `Exchange Deposit (87%)`, `Mixer Contract (99%)`.

---

## 3. Real-World Legal & Operational Implementations

---

### 3.1. TRON (TRC-20 USDT) & Bitcoin (UTXO) Provider Integration

#### Why Critical:
* **The Reality**: In real Indian cybercrime cases (1930 / National Cyber Crime Reporting Portal complaints, task scams, illegal betting apps, and loan apps), **over 70% of illicit fund movement occurs on the TRON network using TRC-20 USDT**, followed by Bitcoin.
* **Implementation**:
  * Add `TronProvider` via TronGrid API (`apps/api/src/providers/tron.py`) tracking TRC-20 `Transfer(address,address,uint256)` smart contract logs.
  * Add `BitcoinProvider` via Blockstream/Electrum RPC with a UTXO-to-Account mapping abstraction.

---

### 3.2. Statutory Section 63 BSA / 65B Evidence Certificate Generator

#### Why Critical:
* Under Indian law (formerly Section 65B of the Indian Evidence Act, now **Section 63 of Bharatiya Sakshya Adhiniyam 2023**), electronic evidence submitted in court without a signed cryptographic hash certificate is inadmissible.
* **Implementation**:
  * Generates an automated statutory certificate containing:
    1. **Cryptographic SHA-256 Hash** of the raw transaction records and Neo4j graph state.
    2. **Hash Chain & Merkle Root** verifying no records were altered post-extraction.
    3. **System Environment Metadata**: UTC timestamps, node RPC endpoints, block numbers, software version.
    4. **Formal Legal Declaration** formatted for courtroom submission by the Investigating Officer (IO).

---

### 3.3. Automated Legal Notice / Freeze Requisition Generator (Section 91 CrPC / Section 94 BNSS)

#### Why Critical:
* When an exchange (e.g., Binance, WazirX, CoinDCX, Kraken) is identified, investigators have a short time window before the suspect liquidates into fiat. Writing legal freeze notices manually causes fatal delays.
* **Implementation**:
  * One-click button in the UI: **"Generate Section 91 Requisition / Freeze Notice"**:
    * Automatically fills the exchange's legal desk email (e.g., `case-intake@binance.com`, `lawenforcement@wazirx.com`).
    * Pre-populates suspect deposit addresses, exact deposit transaction hashes, timestamps, and FIR/Crime numbers.
    * Formatted under **Section 91 CrPC / Section 94 Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023** demanding immediate freezing of accounts and preservation of KYC/IP logs.

---

### 3.4. P2P & OTC Escrow Correlation (1930 Portal / Indian Banking Integration)

#### Why Critical:
* Fraudsters frequently cash out via P2P crypto desks (Binance P2P, Telegram OTC desks), receiving fiat directly into Indian mule bank accounts (UPI / IMPS).
* **Implementation**:
  * **Temporal Correlation Matcher**: Cross-references victim UPI/IMPS transaction timestamps from the **National Cyber Crime Reporting Portal (1930 / I4C)** with blockchain USDT release timestamps (within a $\pm 10\text{-minute}$ window) to link bank accounts to specific on-chain crypto escrow releases.

---

### 3.5. Real-Time Mempool & Watchlist Alerting Engine

#### Why Critical:
* When suspect wallets hold stolen funds, investigators must be alerted the exact moment those funds move.
* **Implementation**:
  * WebSocket / Webhook listeners (via Alchemy Webhooks / QuickNode Streams / ZeroMQ).
  * Triggers instant alerts (Telegram, SMS, Email, In-app webhook) when a watchlisted wallet broadcasts an outgoing transaction in the mempool.

---

### 3.6. Cross-Chain Bridge Event Matcher

#### Why Critical:
* Laundering flows break when funds enter a bridge (e.g., Avalanche Bridge, Arbitrum Gateway, Polygon PoS, Hop Protocol).
* **Implementation**:
  * Correlates the `Deposit`/`Lock` event on Chain A with the corresponding `Mint`/`Unlock` event on Chain B using deposit transaction hashes, normalized token values, and bridge contract signatures.

---

## 4. Master Feature Comparison Matrix

| Capability / Scenario | Basic Shortest Path | Current TRACE-X | Target TRACE-X Master Suite |
| :--- | :---: | :---: | :---: |
| **Linear Multi-Hop Tracing** | ✅ Yes | ✅ Yes (Dijkstra) | ✅ Yes (Flow-Weighted Dijkstra) |
| **Smurfing (1-to-N Splits)** | ❌ Fails (picks 1) | ⚠️ Partial | ✅ **Full Taint Propagation & Max-Flow** |
| **Burner Wallet Syndicates (1000s)** | ❌ Graph explodes | ⚠️ High hop latency | ✅ **Union-Find Entity Clustering** |
| **Peel Chains & Structured Cycles** | ❌ Misses pattern | ⚠️ Factor heuristic | ✅ **VF2 Temporal Motif Mining** |
| **Zero-Day Laundering Behaviors** | ❌ Blind | ❌ Blind | ✅ **Temporal GNN (EvolveGCN)** |
| **Tron TRC-20 & Bitcoin Support** | ❌ No | ❌ EVM-only | ✅ **Full Multi-Chain (Tron/BTC/EVM)** |
| **Courtroom Legal Compliance** | ❌ Generic text | ⚠️ Basic PDF | ✅ **Section 63 BSA / 65B Signed Package** |
| **Exchange Freeze Notice Generation** | ❌ Manual | ❌ Manual | ✅ **1-Click Section 91 CrPC / 94 BNSS** |
| **P2P Fiat / UPI Bank Account Match** | ❌ No | ❌ No | ✅ **I4C / 1930 Portal Time Correlation** |
| **Live Fund Movement Alerting** | ❌ Historical only | ❌ Historical only | ✅ **Real-Time Mempool Watchlist Webhooks** |

---

## 5. Phased Implementation Roadmap

```
Phase 1: Graph Core
├── Value-Weighted Dijkstra
├── Taint Engine (Haircut + FIFO)
└── Union-Find Wallet Clustering

Phase 2: Real-World Readiness
├── Tron TRC-20 & Bitcoin Providers
├── Section 63 BSA / 65B Certificate Generator
└── Section 91 CrPC / 94 BNSS Notice Generator

Phase 3: Deep Intelligence & Automation
├── VF2 Temporal Motif Mining
├── Real-Time Mempool Watchlist Engine
├── Cross-Chain Bridge Event Matcher
└── Temporal GNN (EvolveGCN) Classification
```

---

## 6. SIH 2026 & Law Enforcement Pitch Summary

> *"TRACE-X solves the fundamental operational bottlenecks of crypto crime investigations:*  
> 1. *It replaces simple hop searches with **Flow-Weighted Graph Analytics, Taint Propagation, and Entity Clustering**.*  
> 2. *It bridges on-chain analytics with the real world through **Tron TRC-20 support, P2P fiat correlation, and automated Section 91 CrPC legal notices**.*  
> 3. *It delivers **courtroom-admissible Section 63 BSA / 65B cryptographic evidence packages** within the critical golden hour of fund movement."*
