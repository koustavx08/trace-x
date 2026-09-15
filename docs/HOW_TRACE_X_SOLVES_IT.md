# TRACE-X: How We Solve Crypto Fraud, Our MVPs & Niche Differentiators

> **Platform:** Real-Time Cryptocurrency Fraud Attribution & Investigation Platform  
> **Problem Statement ID:** SIH26183  
> **Target Audience:** Cybercrime Investigators, Law Enforcement Analysts, Supervisory Inspectors  

---

# PART 1: THE LAYMAN’S GUIDE

## 1. How TRACE-X Solves the Problem (The Plain English Story)

Imagine a bank robbery where the thief grabs $50,000 in cash. Instead of running home, the thief runs into an underground subway network, changes clothes 5 times, splits the money into 20 backpacks carried by 20 accomplices, and hops onto different trains. 

An ordinary police officer standing at the station entrance with a flashlight would take weeks to check every subway car. Meanwhile, the thieves have already taken the trains to the airport and bought plane tickets.

**TRACE-X is like turning on a city-wide smart satellite system that lights up the entire subway network in 2 seconds:**
1. **The Instant Search:** The officer types in the scammer's wallet address (`0xSuspect...`).
2. **Automated Tracking:** TRACE-X instantly follows every single trail, backpack, and train simultaneously up to 10 stops deep.
3. **Spotting Criminal Tricks:** It automatically spots tricks—like when someone slowly peels off small bills at every stop (*peel chains*) or jumps from one train line to another (*cross-chain bridges*).
4. **Finding the Exit Gate:** It finds the nearest "airport ticket counter" (**centralized crypto exchange like Binance, Kraken, or CoinDCX**) where someone must show their passport to leave.
5. **The Court-Ready File:** It hands the officer an official legal paper (like a Section 91 CrPC notice) pre-filled with the exact transaction numbers and timestamps, saying: *"Binance ticket counter #4 received the stolen money 12 minutes ago. Send this notice now to freeze their account!"*

---

## 2. Our MVPs in Layman’s Terms (What the User Sees and Uses)

The **Minimum Viable Product (MVP)** is the core toolkit an officer needs on day one to solve cases:

1. **The Investigation Dossier (Case Manager):**
   * Officers can organize multiple complaints under formal case numbers (e.g., `Case #2026-CR-0891: Victim Alice`).
   * Saves suspect wallets, incident dates, amounts, and notes in one secure vault.
2. **Automated Fund Flow Tracker (Multi-Hop Tracing):**
   * No more opening 50 browser tabs on Etherscan. With one click, the system follows the money 3, 5, or 10 steps deep automatically.
3. **Interactive Crime Map (Visual Transaction Graph):**
   * A visual diagram showing wallets as circles and money transfers as arrows.
   * Color-coded: Red for the scammer, Orange for suspicious burner wallets, Blue for token swap pools, and Green for crypto exchanges.
4. **Suspicion Meter (Explainable Risk Score):**
   * A clear score from 0 to 100 telling the officer how suspicious each wallet is, with bullet points explaining why (e.g., *"Used Tornado Cash mixer"*, *"Money moved within 3 minutes"*).
5. **Exchange Finder (VASP Attribution):**
   * Pinpoints which exchange got the money (e.g., Binance, WazirX, Kraken) and how confident the software is (`CONFIRMED`, `HIGH CONFIDENCE`, or `PROBABLE`).
6. **Smart AI Assistant (Virtual Detective Partner):**
   * A chat window where an officer can ask: *"Where did the money go after hop 2?"* or *"Summarize this case for the judge"*, and it answers using only hard evidence from the case.
7. **One-Click Court Report (Export to Legal PDF):**
   * Generates a ready-to-print legal notice that officers can immediately email to Binance's legal department or present to a judge.

---

## 3. Our "Niche" Superpowers in Layman’s Terms (Why We Beat Existing Tools)

Multi-million dollar corporate tools (like Chainalysis or Elliptic) exist, but they have major flaws for law enforcement:

| Competitor Flaw | TRACE-X Niche Superpower |
|---|---|
| **"Black-Box" Scores:** Commercial tools say *"Risk: 87"* without explaining why. Defense lawyers tear this apart in court because the officer cannot explain the math. | **100% Explainable Evidence:** TRACE-X never outputs a number without showing the exact transactions and math behind it. It is built to stand up in a court of law. |
| **Never-Ending Graph Clutter:** Most tools show a giant hairball of thousands of transactions, overwhelming the detective. | **"Nearest Exit" Focus (Dijkstra Shortest Path):** TRACE-X doesn't waste time analyzing every random wallet. It hunts down the **shortest path to a KYC exchange**, because that is the only place an arrest can be made. |
| **Expensive Enterprise Licenses:** Chainalysis costs $50,000–$100,000+ per year per seat, which small police stations cannot afford. | **Open, Accessible & Government-Ready:** Built using open standards, containerized with Docker, and affordable for any police cyber cell. |
| **AI That Hallucinates:** Generic AI tools (like ChatGPT) make up fake wallet addresses and fake transaction hashes. | **Grounded Evidence-Only AI:** The TRACE-X AI assistant is mathematically locked. It can *only* speak about the actual transactions discovered on the blockchain for that case. |

---
---

# PART 2: THE TECHNICAL GUIDE

## 1. Architectural Pipeline & How We Solve It Under the Hood

The TRACE-X architecture handles asynchronous data ingestion, graph construction, algorithmic attribution, and report rendering across a modern distributed stack:

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                 TRACE-X REACT FRONTEND                  │
                  │       (Next.js 14, React Flow, Zustand, TanStack)       │
                  └────────────────────────────┬────────────────────────────┘
                                               │ HTTP / REST
                                               ▼
                  ┌─────────────────────────────────────────────────────────┐
                  │                   FASTAPI BACKEND                       │
                  │         (Async Python 3.11, SQLAlchemy, Pydantic)       │
                  └──────┬─────────────────────┬────────────────────┬───────┘
                         │                     │                    │
            ┌────────────┴──────────┐          │                    │
            ▼                       ▼          ▼                    ▼
┌──────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│ BLOCKCHAIN PROVIDERS │ │       POSTGRESQL        │ │       NEO4J GRAPH       │
│   (Alchemy/Infura)   │ │ (Relational App State,  │ │ (Nodes: Wallet, Tx,     │
│  - EVM JSON-RPC      │ │  Users, Cases, Reports, │ │  Entity; Edges: SENT,   │
│  - Alchemy Asset API │ │  Audit Logs)            │ │  RECEIVED, BELONGS_TO)  │
└──────────────────────┘ └─────────────────────────┘ └─────────────────────────┘
            │                                                       ▲
            └────────────── Ingestion & Cypher ETL ─────────────────┘
```

### The 6-Step Automated Pipeline:
1. **Validation & Normalization (`src/core/validation.py`):**
   - Validates input against EIP-55 checksum standards.
   - Infers network/chain ID (Ethereum Mainnet `1`, Polygon `137`).
2. **Recursive Breadth-First Ingestion (`src/services/wallet_analysis.py`):**
   - Calls Alchemy Asset Transfers API to retrieve outgoing EVM transactions.
   - Traverses $N$-hops recursively with cycle detection, configurable depth ($1 \le d \le 10$), and value floor filtering to discard dusting noise.
3. **Graph Materialization (`src/graph/repository.py`):**
   - Upserts nodes into Neo4j: `(:Wallet)`, `(:Transaction)`, and `(:Entity)`.
   - Creates directional relationships: `(:Wallet)-[:SENT]->(:Transaction)-[:RECEIVED]->(:Wallet)`.
4. **Pattern Matching & Risk Scoring (`src/analytics/risk_engine.py`):**
   - Executes APOC Cypher queries to detect structural laundering patterns (peel chains, rapid sub-5-minute transfers, round ETH numbers, mixer pools).
   - Computes deterministic composite risk: $\text{Score} = \sum (\text{factor\_score}_i \times \text{weight}_i)$.
5. **Shortest Path VASP Attribution (`src/analytics/attribution_engine.py`):**
   - Runs Dijkstra's / shortest path algorithm in Neo4j to find the minimal cost/hop distance from $V_{\text{suspect}}$ to any labeled $V_{\text{vasp}}$.
   - Calculates calibrated confidence metrics based on path length and entity verification grade.
6. **Constrained AI Synthesis & Report Compilation (`src/ai/api.py`, `src/reports/generator.py`):**
   - Passes the extracted subgraph and risk metrics as structured context to the evidence-grounded AI assistant.
   - Compiles formal legal outputs in JSON, Markdown, and court-admissible Section 91 formats.

---

## 2. Core MVP Modules (Technical Specifications)

### MVP 1: EVM Blockchain Provider & Normalization Engine
* **Source:** `apps/api/src/providers/`
* **Functionality:** Abstracts RPC and SDK differences between Alchemy and Infura via a Factory Pattern (`ProviderFactory`). Standardizes raw hexadecimal payloads into Pydantic models with normalized timestamps, gas costs, token decimals (ERC-20/USDT/USDC), and block heights.

### MVP 2: Dual-Database Persistence Architecture
* **Relational Layer (PostgreSQL 15):** Uses SQLAlchemy 2.0 async sessions (`AsyncPG`) to enforce ACID compliance for user authentication (JWT/RS256), multi-tenant case metadata, and immutable forensic audit logs.
* **Graph Layer (Neo4j 5.15):** Optimized for multi-hop graph traversals, indexed on `Wallet(address, chain)`, `Transaction(tx_hash)`, and `Entity(address, chain)`.

### MVP 3: The 12-Factor Deterministic Risk Engine
* **Source:** `apps/api/src/analytics/risk_engine.py`
* Calculates objective risk through weighted factor matrices:
  1. *Mixer Interaction* (weight: `0.25`)
  2. *Peel Chain Obfuscation* (weight: `0.20`)
  3. *OFAC Sanctions Hit* (weight: `0.30`)
  4. *Known High-Risk Entity Association* (weight: `0.15`)
  5. *Rapid Transfer Cadence (<5 min)* (weight: `0.10`)
  6. *Round Amount Structuring* (weight: `0.08`)
  7. *Large Value Transfer (>100 ETH)* (weight: `0.07`)
  8. *Cross-Chain Bridge Lock/Mint* (weight: `0.05`)
  9. *Contract / DEX Interaction* (weight: `0.05`)
  10. *New / Ephemeral Wallet Age* (weight: `0.03`)
  11. *Low-Liquidity Token Swaps* (weight: `0.02`)
  12. *Dusting Transfer Pattern* (weight: `0.02`)

### MVP 4: Shortest Path VASP Attribution Engine
* **Source:** `apps/api/src/analytics/attribution_engine.py` & `src/graph/queries.py`
* Resolves destination addresses against an Entity Intelligence Registry containing 50+ centralized exchange cold/hot/sweep clusters (Binance, Kraken, Coinbase, WazirX, etc.).
* Implements Path Penalty Decay: Confidence decays proportionally with hop distance:
  $$\text{Confidence} = \text{BaseEntityConfidence} \times (1 - \text{hop\_penalty})^{\text{distance}-1}$$
* Output categories: `CONFIRMED`, `HIGH_CONFIDENCE`, `PROBABLE`, `UNKNOWN`.

### MVP 5: Evidence-Grounded AI Investigation Copilot
* **Source:** `apps/api/src/ai/`
* Bounded query classifier categorizes prompts into 8 deterministic intents: `risk`, `attribution`, `patterns`, `flow`, `entity`, `case`, `timeline`, `comparison`.
* Injects structured graph metrics directly into prompts; prohibits the LLM from hallucinating unverified on-chain data.

---

## 3. Our Technical "Niche" Differentiators

### Niche 1: Deterministic Evidence Grounding vs. Black-Box Neural Scores
Most commercial tools use proprietary deep learning models trained on proprietary datasets. When a defense attorney asks in court: *"Why did the software flag this transaction as 85% illicit?"*, the investigator cannot explain the weights.  
**TRACE-X's Niche:** Every factor has a deterministic Cypher query and transaction proof. The system generates an exact mathematical audit formula that any forensic accountant can recompute and verify.

### Niche 2: VASP-Centric Dijkstra Traversal (Target-Oriented Pathfinding)
Standard blockchain explorers perform uniform radial expansion ($O(b^d)$ branching explosion). TRACE-X applies targeted shortest-path algorithms prioritizing nodes marked with exchange clustering heuristics, drastically cutting compute latency from hours to sub-second responses.

### Niche 3: Hybrid Polyglot Storage (ACID Relational + Cypher Graph)
Rather than forcing graph data into relational tables with slow recursive SQL CTEs, or putting user auth and audit logs into a schema-less graph, TRACE-X cleanly divides workloads:
* PostgreSQL guarantees strict legal chain of custody and tamper-evident audit logs.
* Neo4j handles topological subgraphs and community clustering.

### Niche 4: Turnkey Legal Instrumentation (Section 91 CrPC / Subpoena Generator)
Existing tools export CSV dumps of transactions. TRACE-X directly maps on-chain cryptographic proof into ready-to-serve statutory templates (Section 91 CrPC for Indian Law Enforcement, Subpoena Duces Tecum for US/International courts), bridging the gap between digital forensics and statutory criminal procedure.
