# TRACE-X Judge Q&A Preparation

## Core Technical Questions

### Q1: "How do you identify an exchange/VASP?"

**Answer**:
> TRACE-X uses a multi-layered approach to VASP identification:
>
> 1. **Entity Registry**: 50+ pre-loaded entities (exchanges, mixers, bridges, DeFi protocols, sanctioned addresses) with source attribution and confidence levels
> 2. **Graph Traversal**: Dijkstra's shortest-path algorithm on the transaction graph finds paths from suspect wallet to known VASP nodes
> 3. **Confidence Scoring**: Combines entity registry confidence (CONFIRMED/HIGH_CONFIDENCE/PROBABLE/UNKNOWN), path length penalty, attribution type weight, and value factor
> 4. **Evidence Packaging**: Every attribution includes on-chain path evidence, off-chain intelligence source, and confidence breakdown
>
> **Key Principle**: The system never claims ownership without evidence. Attributions are probabilistic with explicit confidence levels (CONFIRMED/HIGH_CONFIDENCE/PROBABLE/UNKNOWN).

---

### Q2: "Is the AI hallucinating?"

**Answer**:
> **No, the AI is evidence-grounded and constrained.**
>
> The AI assistant does NOT:
> - Query the blockchain directly
> - Generate facts independently
> - Access external knowledge beyond the investigation context
>
> The AI assistant DOES:
> 1. Receives structured investigation results (risk assessment, attribution, patterns, graph data)
> 2. Classifies the user's query into 8 types (risk, attribution, patterns, flow, entity, case, timeline, comparison)
> 3. Retrieves relevant evidence from the investigation engines
> 4. Generates responses constrained to the provided evidence
> 5. Includes evidence citations and confidence levels in every response
> 5. Suggests follow-up questions based on available data
>
> **Guardrails**: If evidence is insufficient, the AI explicitly states "insufficient evidence" rather than speculating.

---

### Q3: "Why Neo4j? Why not PostgreSQL for graphs?"

**Answer**:
> Blockchain fund movement is **naturally a graph** - wallets and transactions form nodes and edges. Neo4j provides:
>
> 1. **Native Graph Storage**: Wallets, transactions, entities as nodes; SENT/RECEIVED/BELONGS_TO as relationships
> 2. **Efficient Multi-hop Traversal**: Dijkstra/A* shortest path to VASPs in milliseconds vs. recursive CTEs in PostgreSQL
> 3. **Graph Algorithms**: PageRank centrality, Louvain community detection, temporal flow analysis via APOC/GDS
> 4. **Pattern Detection**: Native pattern matching for peel chains, round amounts, mixer interactions
> 5. **Schema Flexibility**: Easy addition of new node/relationship types (e.g., new entity types)
>
> **PostgreSQL** handles: Cases, users, investigation metadata, report storage - relational data where ACID matters.
>
> **Hybrid Approach**: Best of both worlds - relational for investigation metadata, graph for fund flow analysis.

---

### Q4: "Can this support more blockchains?"

**Answer**:
> **Yes. TRACE-X uses a provider abstraction layer.**
>
> Current Implementation:
> - Ethereum (Chain ID 1) - Primary
> - Polygon (Chain ID 137) - Secondary
>
> Adding a new EVM-compatible chain:
> 1. Add chain config to `core/validation.py` (chain_id, name, symbol, explorer, RPC env var)
> 2. Add provider config in `providers/factory.py` (Alchemy/Infura RPC URLs)
> 3. Set environment variables (e.g., `ARBITRUM_RPC_URL`, `OPTIMISM_RPC_URL`)
> 4. No changes to core investigation engine, graph layer, or risk engine
>
> **Non-EVM chains** (Solana, Bitcoin, Tron) would require new provider implementations but the abstraction pattern supports it.

---

### Q5: "How is the risk score calculated?"

**Answer**:
> **Deterministic, explainable, weighted factor analysis.**
>
> **12 Risk Factors** with explicit weights:
> | Factor | Weight | Description |
> |--------|--------|-------------|
> | Mixer Interaction | 0.25 | Tornado Cash, Railgun, Wasabi detection |
> | Peel Chain | 0.20 | Multi-hop fan-out patterns |
> | Sanctions Hit | 0.30 | OFAC SDN list matches |
> | High-Risk Entity | 0.15 | Known mixer/darknet/gambling entities |
> | Rapid Movement | 0.10 | Sub-5-minute transaction sequences |
> | Round Amounts | 0.08 | Multiple round-number ETH transfers |
> | Large Value Transfer | 0.07 | Transfers >100 ETH |
> | Cross-Chain Bridge | 0.05 | Polygon, Arbitrum, Optimism bridges |
> | Contract Interaction | 0.05 | High DEX/protocol contract usage |
> | New Wallet | 0.03 | <30 days old, <5 transactions |
> | Low Liquidity Token | 0.02 | Illiquid token interactions |
> | Dusting Attack | 0.02 | Micro-transfer patterns |
>
> **Scoring**: Each factor = base_score × weight. Overall = Σ(weighted_scores), capped at max factor score.
>
> **Severity Thresholds**: CRITICAL≥80, HIGH≥60, MEDIUM≥40, LOW≥20, INFO<20
>
> **Explainability**: Every factor includes description, evidence, and confidence level. No black-box ML.

---

### Q6: "How do you handle mixer/tumbler detection?"

**Answer**:
> **Multi-layered approach:**
>
> 1. **Known Mixer Registry**: Tornado Cash contracts, Railgun, Wasabi, Samourai Whirlpool in entity registry (CONFIRMED confidence)
> 2. **Graph Traversal**: Dijkstra pathfinding detects paths to mixer nodes within trace depth
> 3. **Pattern Detection**: 
>    - Sudden value reduction (peel chain into mixer)
>    - Equal-value outputs (coinjoin signature)
>    - Rapid deposit/withdrawal cycles
> 4. **Entity Linking**: Wallets interacting with mixer contracts get `entity_type: mixer`, `attribution_status: attributed`
> 5. **Risk Scoring**: Mixer interaction = highest weight factor (0.25), CRITICAL severity
>
> **Limitation**: Only detects *known* mixers. Novel/private mixers require heuristic detection.

---

### Q7: "How do you prevent false positives?"

**Answer**:
> **Multi-layered validation:**
>
> 1. **Address Validation**: EIP-55 checksum + eth-utils validation before any API call
> 2. **Provider Validation**: Live RPC call to confirm address exists on chain
> 3. **Deduplication**: Wallet deduplication per case (address + chain unique constraint)
> 4. **Confidence Propagation**: Entity confidence propagates through graph edges with penalty per hop
> 5. **Evidence Requirement**: Attribution requires on-chain path + entity registry match
> 6. **Confidence Levels**: Explicit CONFIRMED/HIGH_CONFIDENCE/PROBABLE/UNKNOWN - never claims certainty
> 7. **Human-in-the-loop**: Analyst must review and confirm attributions before report generation
>
> **False Positive Mitigation**: 
> - Exchange deposit addresses often reused → entity registry prevents re-attribution
> - Contract interactions filtered from wallet-to-wallet tracing
> - Minimum value thresholds filter dust transactions

---

### Q8: "What about privacy/GDPR?"

**Answer**:
> **TRACE-X processes only public blockchain data:**
>
> 1. **No PII Collection**: Only public wallet addresses, transaction hashes, public entity labels
> 2. **No Private Keys**: Never handles private keys, mnemonics, or signs transactions
> 3. **No Custody**: Does not hold, transfer, or manage funds
> 4. **Audit Trail**: Every investigation action logged (who, what, when, evidence)
> 5. **Data Retention**: Configurable retention policies for investigation data
> 6. **Access Control**: Role-based access (analyst/supervisor/admin)
>
> **Compliance**: Designed for law enforcement use under legal authority (subpoena, warrant). Not for general public surveillance.

---

### Q9: "How does this scale?"

**Answer**:
> **Horizontal scaling architecture:**
>
> **Backend**: Stateless FastAPI workers (Celery) - scale horizontally
> - Analysis tasks queued via Redis
> - Worker pools per queue (analysis, graph, reports, enrichment)
>
> **Database**: 
> - PostgreSQL: Connection pooling (10-30 connections), read replicas for reads
> - Neo4j: Enterprise edition for clustering, read replicas for graph queries
>
> **Caching**: Redis for API responses, entity lookups, session storage
>
> **Blockchain Providers**: 
> - Alchemy/Infura rate limits managed via token bucket
> - Automatic fallback (Alchemy → Infura)
> - Request batching for transaction fetches
>
> **Benchmarks** (target):
> - Wallet analysis (5 hops, 1000 txs): <30 seconds
> - Graph shortest path: <500ms
> - Risk assessment: <2 seconds
> - Report generation: <10 seconds

---

### Q10: "What are the limitations?"

**Answer**:
> **Honest limitations:**
>
> 1. **Provider Dependency**: Requires Alchemy/Infura API keys (rate limits, cost)
> 2. **Known Entity Coverage**: Only detects entities in registry (~50 entities). Novel exchanges/mixers need manual addition
> 3. **Trace Depth**: Limited to 5-10 hops (configurable). Deep layering may not be fully traced
> 4. **Cross-chain Gaps**: Bridge detection relies on known bridge contracts
> 5. **No ML Model**: Risk scoring is rule-based. No behavioral anomaly detection yet
> 6. **No Real-time Monitoring**: Batch analysis on-demand, not streaming
> 7. **Single-tenant**: Multi-tenancy not implemented (future work)
> 8. **English Only**: AI assistant and UI English-only
> 9. **No Mobile App**: Web-only interface
> 10. **Demo Data**: Synthetic data only - no real blockchain analysis without API keys

---

### Q11: "Why not use ML for risk scoring?"

**Answer**:
> **Explainability > Accuracy for investigations.**
>
> - **Legal Requirement**: Investigators must explain *why* a wallet is high-risk in court
> - **Auditability**: Every factor traceable to specific transactions and evidence
> - **No Black Box**: Rule-based = auditable, debuggable, defendable
> - **Regulatory**: Many jurisdictions require explainable AI for law enforcement tools
>
> **Future**: ML can augment (anomaly detection, clustering) but final scoring remains rule-based with ML as additional evidence factor.

---

### Q12: "How do you handle cross-chain tracing?"

**Answer**:
> **Bridge-aware graph traversal:**
>
> 1. **Bridge Registry**: Known bridges (Polygon, Arbitrum, Optimism, BSC, Wormhole) in entity registry as `entity_type: bridge`
> 2. **Bridge Detection**: Transaction pattern matching (lock/mint, burn/release events)
> 3. **Cross-chain Graph**: Wallets on different chains linked via bridge transactions
> 4. **Unified Trace**: Single investigation can span Ethereum → Polygon → BSC
> 5. **Value Tracking**: Tracks value across bridges (accounting for fees, slippage)
>
> **Limitation**: Only detects *known* bridges. Novel bridges require manual addition.

---

## Quick Reference Card

| Question | 30-Second Answer |
|----------|------------------|
| **Identify exchange?** | Entity registry + graph shortest path + confidence scoring |
| **AI hallucinating?** | No - evidence-grounded, constrained to investigation data |
| **Why Neo4j?** | Native graph for fund flow, multi-hop traversal, graph algorithms |
| **More chains?** | Provider abstraction layer - add config + RPC URL |
| **Risk score?** | 12 weighted factors, deterministic, explainable, no ML |
| **Mixer detection?** | Known registry + graph traversal + pattern detection |
| **False positives?** | Validation, deduplication, confidence propagation, human review |
| **Privacy/GDPR?** | Public data only, no keys, no custody, audit trail |
| **Scale?** | Stateless workers, Neo4j clustering, Redis caching |
| **Limitations?** | Provider deps, known entities only, trace depth limits |
| **ML for risk?** | No - explainability required for legal defensibility |
| **Cross-chain?** | Bridge registry + unified graph + value tracking |

---

## Demo-Specific Questions

### "Is this real blockchain data?"

> **In demo mode**: Synthetic data seeded for demonstration. All addresses, transactions, and patterns are fabricated but structurally realistic.
> 
> **In production**: Connects to Alchemy/Infura for real-time blockchain data. The analysis engine is identical.

### "Can I try it with my own address?"

> **Yes** - Enter any EVM address (0x...) in the Analyze page. Requires valid Alchemy/Infura API keys for live data. Demo mode uses pre-seeded data.

### "How long does analysis take?"

> **Demo**: Pre-computed results load instantly.
> 
> **Live**: 10-30 seconds for 5-hop, 1000-transaction analysis depending on provider latency.

### "Is this open source?"

> **Not currently**. TRACE-X is a prototype for SIH 2026. Architecture documentation available in `docs/ARCHITECTURE.md`.