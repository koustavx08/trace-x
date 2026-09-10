# TRACE-X: Problem & Solution

## Problem Statement

### The Cryptocurrency Fraud Investigation Crisis

Law enforcement and compliance teams face an unprecedented challenge: **cryptocurrency has become the primary payment method for cybercrime**, but investigation tools have not kept pace.

> **"We have the wallet address. Now what?"** — Every investigator's first question

### Current Investigation Pain Points

| Challenge | Current Reality | Impact |
|-----------|----------------|--------|
| **Manual tracing** | Investigators manually follow transactions across explorers | Days/weeks per case; human error; incomplete traces |
| **No pattern detection** | Visual inspection only | Miss peel chains, layering, mixer usage |
| **Exchange identification** | Manual lookup, guesswork | Cannot legally compel exchange without evidence |
| **Cross-chain blindness** | Single-chain tools | Funds move across Ethereum → Polygon → BSC unseen |
| **No risk prioritization** | All wallets equal | Critical threats buried in noise |
| **Non-explainable tools** | Black-box ML scores | Inadmissible in court; cannot defend in testimony |
| **Siloed intelligence** | Entity data scattered | Duplicate work, missed connections |
| **No audit trail** | Manual notes | Evidence chain broken; inadmissible |

---

## The TRACE-X Solution

### One Platform. Complete Investigation.

TRACE-X transforms a **single wallet address** into a **structured, evidence-grounded investigation** — automatically.

```
Wallet Address
      ↓
┌─────────────────────────────────────────────┐
│  TRACE-X INVESTIGATION ENGINE               │
├─────────────────────────────────────────────┤
│  1. VALIDATE & ENRICH                       │
│     • Address validation (EIP-55)           │
│     • Chain detection                       │
│     • Balance & token holdings              │
├─────────────────────────────────────────────┤
│  2. BLOCKCHAIN TRACING                      │
│     • Recursive fund flow (configurable hops)│
│     • Transaction ingestion (PostgreSQL)    │
│     • Graph construction (Neo4j)            │
├─────────────────────────────────────────────┤
│  3. INTELLIGENCE LAYER                      │
│     • Entity registry (50+ exchanges, etc.) │
│     • Pattern detection (peel, mixer, etc.) │
│     • Risk scoring (12 factors, weighted)   │
├─────────────────────────────────────────────┤
│  4. ATTRIBUTION ENGINE                      │
│     • Shortest path to VASP (Dijkstra)      │
│     • Confidence scoring                    │
│     • Evidence packaging                    │
├─────────────────────────────────────────────┤
│  5. AI INVESTIGATION ASSISTANT              │
│     • Evidence-grounded Q&A                 │
│     • Narrative report generation           │
│     • Follow-up suggestions                 │
├─────────────────────────────────────────────┤
│  6. REPORT GENERATION                       │
│     • Executive summary                     │
│     • Technical findings                    │
│     • Evidence package (court-ready)        │
└─────────────────────────────────────────────┘
      ↓
Investigation Report + Graph + Evidence Package
```

---

## Core Innovation

### 1. Evidence-Grounded, Not Black-Box

| Traditional Tools | TRACE-X |
|-------------------|---------|
| "Risk Score: 87" | "Risk: 91.2 — CRITICAL: Mixer interaction (Tornado Cash, 0.25 weight), Peel chain detected (5 hops), Round amounts (7 transactions)" |
| "Exchange: Binance" | "Nearest VASP: Binance — CONFIRMED (94.2%), 4 hops, 48,500 ETH. Evidence: [on-chain path, entity registry, KYC correlation]" |
| "High Risk" | "Factors: Mixer (CRITICAL, 0.25), Peel Chain (HIGH, 0.20), Rapid Movement (MEDIUM, 0.10). Each with transaction evidence." |

**Every conclusion cites evidence. Every score is explainable.**

---

### 2. Blockchain-Native Graph Intelligence

```
Wallet (A) ──SENT──→ Transaction ──RECEIVED──→ Wallet (B)
    │                                               │
    │                                               │
    ▼                                               ▼
Entity: "Attacker"                          Entity: "Binance"
Type: mixer (CONFIRMED)                     Type: exchange (CONFIRMED)
```

- **Native graph storage** (Neo4j): Wallets, transactions, entities as nodes
- **Relationships**: SENT, RECEIVED, BELONGS_TO
- **Algorithms**: Dijkstra shortest path, PageRank, Louvain communities, temporal analysis
- **Multi-hop tracing**: Configurable depth (1-10 hops), value thresholds, duplicate protection

---

### 3. Explainable Risk Scoring (12 Factors)

| Factor | Weight | Example Trigger |
|--------|--------|-----------------|
| Mixer Interaction | 0.25 | Tornado Cash, Railgun, Wasabi |
| Peel Chain | 0.20 | 5+ hops, fan-out pattern |
| Sanctions Hit | 0.30 | OFAC SDN match |
| High-Risk Entity | 0.15 | Known mixer/darknet/gambling |
| Rapid Movement | 0.10 | <5 min between txs |
| Round Amounts | 0.08 | 7+ round-number ETH txs |
| Large Transfer | 0.07 | >100 ETH single tx |
| Cross-Chain Bridge | 0.05 | Polygon, Arbitrum, Wormhole |
| Contract Interaction | 0.05 | High DEX/protocol usage |
| New Wallet | 0.03 | <30 days, <5 txs |
| Low Liquidity Token | 0.02 | Illiquid token swaps |
| Dusting Attack | 0.02 | Micro-transfer patterns |

**Score = Σ(factor_score × weight)**, capped at max factor score.  
**Thresholds**: CRITICAL≥80, HIGH≥60, MEDIUM≥40, LOW≥20, INFO<20

---

### 4. VASP Attribution with Confidence

```
Suspect Wallet (0xa241...)
    │
    ├─→ Uniswap V3 (0x1f98...) ──→ 0xA0b8... (Polygon Bridge)
    │                                    │
    │                                    ▼
    │                              0xC02a... (WETH)
    │                                    │
    │                                    ▼
    └──────────────────────────────────→ 0x28C6... (Binance Deposit)
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │ VASP: Binance   │
                                    │ Confidence:     │
                                    │ CONFIRMED       │
                                    │ 94.2%           │
                                    │ 4 hops          │
                                    │ 48,500 ETH      │
                                    └─────────────────┘
```

**Confidence = Entity_Confidence × Path_Penalty × Type_Weight × Value_Factor**

---

### 5. AI Investigation Assistant (Evidence-Grounded)

**Not a chatbot. An investigation co-pilot.**

| Query Type | Example | Response Includes |
|------------|---------|-------------------|
| Risk Summary | "Risk for wallet 0xa241..." | Score, factors, evidence, follow-ups |
| Attribution | "Where did funds from 0x... go?" | VASP, path, confidence, evidence |
| Patterns | "Suspicious patterns on Ethereum?" | Peel chains, round amounts, mixers |
| Fund Flow | "Trace money from 0x..." | Path, hops, value, VASP endpoint |
| Entity Lookup | "Who owns 0x...?" | Entity, type, confidence, source |
| Case Overview | "Case TRX-20240115-0042" | Stats, wallets, investigations |
| Timeline | "Timeline for wallet 0x..." | Daily volume, peak activity |
| Comparison | "Compare wallet A vs B" | Side-by-side risk/attribution |

**Anti-Hallucination Guardrails**:
- Never queries blockchain directly
- Constrained to investigation evidence
- Explicit confidence levels
- "Insufficient evidence" vs. speculation
- Follow-up questions based on available data

---

### 6. Court-Ready Reports

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

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js 14)                    │
│  Dashboard • Cases • Analyze • Graph • Risk • AI • Reports      │
│  TanStack Query • Zustand • React Flow • shadcn/ui • Tailwind   │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP/JSON
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                        │
│  Cases • Wallets • Analysis • Graph • Risk • AI • Auth          │
│  Pydantic • SQLAlchemy 2.0 • Alembic • JWT • RBAC               │
└─────────────────────────────┬───────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
                              ▼
    ┌─────────────────┐ ┌───────────────┐ ┌─────────────┐
    │   PostgreSQL    │ │    Neo4j      │ │    Redis    │
    │  (Relational)   │ │   (Graph)     │ │  (Cache/    │
    │  Cases, Users,  │ │  Wallets,     │ │   Queue/    │
    │  Wallets, Txns  │ │  Txs, Entities│ │   Sessions) │
    └─────────────────┘ └───────────────┘ └─────────────┘
                              ▲
                              │
                    ┌─────────┴─────────┐
                    │  BLOCKCHAIN       │
                    │  PROVIDERS        │
                    │  Alchemy / Infura │
                    └───────────────────┘
```

---

## SIH 2026 Alignment

### Problem Statement (SIH26183)
> "Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported Suspect Wallet Addresses through Automated Blockchain Analytics"

### TRACE-X Direct Mapping

| SIH Requirement | TRACE-X Implementation |
|-----------------|------------------------|
| Victim-reported suspect wallet | Wallet validation + case creation |
| Real-time identification | Sub-30-second analysis (5 hops, 1000 txs) |
| Fraud-linked exchanges | VASP attribution with confidence |
| Automated blockchain analytics | Recursive tracing + graph analytics + risk scoring |
| Real-time | Sub-30-second end-to-end |

---

## Impact

### For Investigators
- **Time**: Days → Minutes
- **Accuracy**: Manual → Automated + Verified
- **Evidence**: Notes → Hash-linked, court-ready
- **Prioritization**: None → Risk-based triage

### For Organizations
- **Throughput**: 10x case capacity
- **Consistency**: Analyst-dependent → Standardized
- **Training**: Weeks → Hours
- **Collaboration**: Siloed → Shared graph/intelligence

### For Justice
- **Admissibility**: Evidence-grounded, explainable
- **Speed**: Faster asset freezing/seizure
- **Deterrence**: Visible, traceable fund flows
- **Global**: Cross-chain, multi-jurisdiction ready

---

## Competitive Differentiation

| Feature | Chainalysis | CipherTrace | TRACE-X |
|---------|-------------|-------------|---------|
| **Explainable Scoring** | ❌ Black box | ❌ Black box | ✅ 12 factors, weighted |
| **AI Assistant** | ❌ | ❌ | ✅ Evidence-grounded |
| **Graph Visualization** | ✅ | ✅ | ✅ React Flow |
| **Open Architecture** | ❌ Closed | ❌ Closed | ✅ Provider abstraction |
| **On-premise Deploy** | ❌ Cloud only | ❌ Cloud only | ✅ Docker/K8s |
| **Cost** | $$$$ Enterprise | $$$$ Enterprise | 💰 Prototype/Flexible |
| **AI Narrative** | ❌ | ❌ | ✅ Auto-generated reports |

---

## Roadmap (Post-SIH)

### Phase 1 (0-3 months)
- [ ] Multi-tenancy & SSO
- [ ] Real-time monitoring/alerts
- [ ] Bitcoin/Solana support
- [ ] ML anomaly detection (augment rules)

### Phase 2 (3-6 months)
- [ ] Collaborative investigations
- [ ] Advanced ML (clustering, behavioral)
- [ ] Mobile app for field agents
- [ ] API marketplace for entities

### Phase 3 (6-12 months)
- [ ] Global entity consortium
- [ ] Automated legal request generation
- [ ] DeFi protocol-specific analytics
- [ ] NFT/token tracing

---

## Conclusion

TRACE-X solves the **core investigation bottleneck**: turning a wallet address into **actionable, explainable, court-ready intelligence** — automatically.

**Not a black box. Not a toy. A force multiplier for cryptocurrency fraud investigation.**

---

*TRACE-X — SIH 2026 Prototype*  
*Real-Time Cryptocurrency Fraud Attribution & Investigation Platform*