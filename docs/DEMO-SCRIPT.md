# TRACE-X SIH Demo Script

## Overview

**Duration**: 3-5 minutes  
**Audience**: SIH 2026 Judges  
**Format**: Live demo with pre-seeded synthetic data

---

## Demo Flow (3-5 minutes)

### 0:00-0:30 — Problem Statement

> "Cryptocurrency fraud investigations often begin with only a wallet address. Investigators then need to manually analyze transaction histories, trace funds through intermediary wallets, identify suspicious movement patterns, and determine where funds may have reached an exchange. TRACE-X automates this investigation workflow and converts raw blockchain activity into explainable intelligence."

**Visual**: Show dashboard with 5 synthetic cases

---

### 0:30-1:00 — Case Selection & Input

**Action**: Click "Run Full Demo" on **DeFi Protocol Flash Loan Exploit** (TRX-20240115-0042)

**Narration**:
> "We start with a suspect wallet address from a flash loan exploit. The case already has context: crime type, description, and the suspect wallet address."

**Show**: 
- Case card with crime type, status, tags
- Suspect wallet address: `0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb`
- Chain: Ethereum

---

### 1:00-1:45 — Automated Analysis & Blockchain Tracing

**Action**: Click "Run Full Demo" - watch the automated flow

**Narration**:
> "TRACE-X now:
> 1. Validates the address and detects the blockchain (Ethereum)
> 2. Fetches transactions via Alchemy/Infura
> 3. Recursively traces fund movements through 5 hops
> 4. Stores transactions in PostgreSQL and Neo4j
> 5. Runs risk scoring with 12 factor types
> 6. Traces to nearest VASP using graph algorithms
> 7. All in under 30 seconds"

**Show**: 
- Loading states with progress indicators
- Investigation creation and completion
- Transaction count, unique addresses, risk score

---

### 1:45-2:30 — Intelligence & Pattern Detection

**Action**: Navigate to "Patterns" tab in Analyze page

**Narration**:
> "TRACE-X automatically detects suspicious patterns:
> - **Peel Chain**: Funds split across multiple addresses
> - **Round Amounts**: Multiple transactions with round ETH amounts
> - **Mixer Interaction**: Funds traced through Tornado Cash
> - **Rapid Movement**: 4 hops in under 10 minutes"

**Show**:
- Pattern cards with severity badges (High/Medium)
- Evidence links to specific transactions

---

### 2:30-3:15 — VASP Attribution

**Action**: Navigate to "Attribution" tab in Risk page

**Narration**:
> "TRACE-X traces the fund flow to the nearest VASP using Dijkstra's shortest path algorithm on the transaction graph:
> - **Nearest VASP**: Binance (CONFIRMED, 94.2% confidence)
> - **Distance**: 4 hops
> - **Value Traced**: 48,500 ETH
> - **Evidence**: 3 corroborating signals (on-chain path + entity registry + KYC correlation)"

**Key Statement**:
> "TRACE-X does not claim certainty without evidence. It distinguishes between verified blockchain facts, external intelligence labels, and system-generated inference."

**Show**:
- Attribution card with confidence badge (CONFIRMED - green)
- Path visualization: 4 hops to Binance
- Evidence breakdown (on-chain path + entity registry + KYC correlation)

---

### 3:15-3:45 — Risk Assessment

**Action**: Navigate to "Risk" tab

**Narration**:
> "Risk scoring uses 12 weighted factors with confidence-weighted scoring:
> - Mixer Interaction (25% weight): CRITICAL - Tornado Cash detected
> - Peel Chain (20% weight): HIGH - 5-hop fan-out detected
> - Sanctions Hit (30% weight): Not applicable here
> - Overall Score: 91.2/100 (CRITICAL)"

**Show**:
- Risk score gauge (91.2/100 - CRITICAL red)
- Factor breakdown with weighted scores
- Evidence for each factor

---

### 3:45-4:15 — AI Investigation Assistant

**Action**: Navigate to AI Assistant page, ask: "Summarize the investigation and explain why Binance was identified"

**Narration**:
> "The AI assistant receives structured investigation results and provides evidence-grounded responses:
> - Does NOT hallucinate - constrained to system evidence
> - Cites specific evidence for each claim
> - Provides follow-up questions for deeper investigation"

**Show**:
- AI response with evidence citations
- Confidence badges (CONFIRMED/HIGH_CONFIDENCE)
- Follow-up question suggestions

---

### 4:15-4:30 — Report Generation

**Action**: Click "Generate Report" → Select "Technical Findings" template → PDF format

**Narration**:
> "TRACE-X generates structured investigation reports:
> - Executive summary
> - Wallet analysis with risk scores
> - Attribution analysis with evidence
> - Transaction timeline
> - Graph snapshots
> - Methodology & limitations"

**Show**:
- Report generation dialog
- Generated PDF/HTML/JSON download

---

### 4:30-5:00 — Summary & Close

**Narration**:
> "TRACE-X transforms a wallet address into a structured investigation path, helping investigators understand:
> - Where funds moved (graph traversal)
> - Which patterns were detected (automated detection)
> - Which entities may be relevant (VASP attribution)
> - Why (explainable risk scoring with evidence)"

**Closing Statement**:
> "TRACE-X is not a black box. Every attribution, every risk factor, every pattern has evidence you can verify. This is blockchain forensics you can take to court."

---

## Fallback Demo (If Live Demo Fails)

1. **Pre-recorded video** (3 min) - plays full flow
2. **Screenshots** in `docs/demo-screenshots/` - walk through static images
3. **Static data** - Demo page loads pre-computed results instantly
4. **Judge Mode** (`/demo`) - One-click access to all 5 scenarios with pre-computed results

---

## Demo Checklist

- [ ] Docker services running (postgres, neo4j, redis, backend, frontend)
- [ ] Demo seed data loaded (`docker exec tracex-backend python scripts/seed_demo_data.py`)
- [ ] All 5 demo cases visible on `/demo` page
- [ ] "Run Full Demo" works for DeFi Exploit case
- [ ] AI Assistant responds with evidence-grounded answers
- [ ] Report generation works (PDF/HTML/JSON)
- [ ] Graph visualization loads at `/graph?wallet=<id>`
- [ ] Risk page shows factors with evidence
- [ ] Attribution shows Binance with CONFIDENCE badge
- [ ] Graph page loads at `/graph?wallet=<wallet_id>`
- [ ] Dashboard shows live stats from database

---

## Troubleshooting

| Issue | Quick Fix |
|-------|-----------|
| Backend not starting | Check `.env` has valid API keys, check `docker logs tracex-backend` |
| Neo4j connection refused | Wait for healthcheck, check `docker logs tracex-neo4j` |
| No transactions found | Ensure Alchemy/Infura API keys in `.env`, or use demo mode |
| Frontend can't reach API | Check `NEXT_PUBLIC_API_URL` in `.env.local` |
| Neo4j APOC not available | Ensure `NEO4J_PLUGINS: '["apoc"]'` in docker-compose |

---

## Demo URLs

| Page | URL |
|------|-----|
| Dashboard | http://localhost:3000/dashboard |
| Demo Mode | http://localhost:3000/demo |
| Cases | http://localhost:3000/cases |
| Analyze | http://localhost:3000/analyze |
| Graph | http://localhost:3000/graph |
| Risk | http://localhost:3000/risk |
| AI Assistant | http://localhost:3000/ai |
| Reports | http://localhost:3000/reports |
| API Docs | http://localhost:8000/docs |