# TRACE-X: Official SIH Presentation Pitch Script

- **Team:** ZERO_DAY
- **Problem Statement ID:** 26183
- **Title:** Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported Suspect Wallet Addresses through Automated Blockchain Analytics
- **Theme:** Blockchain & Cybersecurity
- **Target Duration:** ~6 to 7 minutes *(with 5-minute emergency trim cues)*

---

### Minute 0:00 – 0:30 | Title & Opening Hook
**[SLIDE 1: Title Slide — SMART INDIA HACKATHON 2026]**

> "Respected Judges, good morning. We are Team **ZERO_DAY**, presenting our solution for Problem Statement **26183**: 'Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported Suspect Wallet Addresses through Automated Blockchain Analytics'.
> 
> In 2024 alone, over **₹1,750 Crore** was lost by Indian citizens to cyber fraud in just the first 4 months according to I4C data, with cryptocurrency becoming the primary exit pipeline for these syndicates.
> 
> To understand why this is happening and how criminals exploit it, we first need to look at how cryptocurrency actually functions."

---

### Minute 0:30 – 1:30 | The Core Concept: How Crypto Functions vs Traditional Money
**[SLIDE 2: EXISTING PROBLEM (Top Banner)]**

> "In traditional banking, money sits in a central database tied to your Aadhaar, PAN, and KYC. A bank manager or a court order can freeze that account with a single click.
> 
> Cryptocurrency is fundamentally different:
> 1. **It is not physical currency:** It is a decentralized, mathematical ledger recorded across thousands of computers worldwide.
> 2. **How a Crypto Account Works:** A wallet doesn't store physical coins. It consists of a **Public Address**—which acts like an account number or UPI ID that anyone can see to send you funds—and a cryptographic **Private Key**, which is the mathematical password that signs and authorizes transfers.
> 3. **Custodial vs. Non-Custodial Wallets (The Critical Distinction):**
>    - **Custodial Accounts:** These are managed by third-party centralized exchanges like Binance or CoinDCX. They hold your private keys on your behalf. Because they are regulated companies, they enforce KYC, and police can legally compel them to freeze funds.
>    - **Non-Custodial / Self-Custody Wallets:** Tools like MetaMask, Trust Wallet, or burner hardware wallets. Anyone on Earth can create one in 10 seconds with **zero KYC, no phone number, and no identity verification**. Only the user holds the private key.
>    - **The Law Enforcement Dilemma:** Because there is no company or bank manager managing a non-custodial wallet, **neither the police nor any government can freeze or seize a non-custodial wallet**."

---

### Minute 1:30 – 2:50 | The Scam Lifecycle, The Tragic Reality & The Golden Period
**[SLIDE 2: Flowchart on the Left & Problem Context]**

> "Now, how does a scam actually happen?
> 
> Whether it is a fake job scam, a 'pig-butchering' investment app, or a phishing drainer, the criminal tricks the victim into sending crypto, or converts stolen fiat money into cryptocurrency.
> 
> The funds immediately land in the scammer's **non-custodial suspect wallet**—the completely anonymous zone where police cannot freeze them.
> 
> Next, to break the trail, the scammer moves the funds through an obfuscation cycle:
> - They run **Peel Chains**—splitting a large sum into small amounts across dozens of intermediary burner wallets.
> - They use **Decentralized Swaps (DEXs)** and **Cross-Chain Bridges** to hop between Ethereum, Polygon, and Tron to confuse block explorers.
> 
> And here is the tragic reality:  
> While criminals move these stolen funds through automated multi-hop laundering chains in **less than 35 minutes**, investigating officers manually take **3 to 5 days** opening dozens of explorer tabs! By the time an FIR is processed or a notice is drafted, the money has already reached its final destination.
> 
> What is that final destination? The **Tollbooth**: a Centralized Exchange, or **VASP** (like Binance, Kraken, or CoinDCX). Criminals cannot spend digital tokens at a local shop; they must convert them into real fiat paper currency (INR or USD). Centralized exchanges are the only place they can off-ramp, and centralized exchanges **have KYC**.
> 
> This creates what cyber investigators call the **'Golden Period'**.  
> The moment stolen crypto lands on an exchange, a ticking clock begins. **During this Golden Period—before the criminal hits 'Withdraw to Bank'—the asset recovery rate is nearly 100% with a single emergency freeze click by the exchange.** But the moment that Golden Period expires and the funds convert into cash or mule accounts, recovery drops to zero.
> 
> Today, because manual tracing takes days, police consistently miss this Golden Period. TRACE-X was built to ensure they never miss it again."

---

### Minute 2:50 – 4:10 | The Solution: TRACE-X & Core Features
**[SLIDE 2: Full View — 6 Core Feature Cards]**

> "This is where **TRACE-X** changes the game. With just a single victim-reported wallet address, our system automates the entire investigation across our core features:
> 
> 1. **Automated Fund Tracing & Graph Intelligence (Combined):**  
>    Instead of manually opening 50 Etherscan tabs, our recursive engine crawls multi-hop outgoing transactions up to 10 hops deep in seconds. It instantly converts this raw blockchain data into an interactive, color-coded **relationship graph using Neo4j**—mapping every wallet, transaction, and entity connection visually so officers can see the entire flow at a glance.
> 
> 2. **Suspicious Pattern Detection:**  
>    TRACE-X automatically flags laundering techniques like rapid sub-5-minute fund movement, peel chains, mixer usage, and fan-out/fan-in trees.
> 
> 3. **Explainable Risk Scoring:**  
>    Rather than giving an arbitrary black-box number, our engine evaluates 12 weighted behavioral factors to generate a 0–100 risk score, explicitly displaying the exact forensic reasons behind the score.
> 
> 4. **VASP & Entity Attribution (The Shortest Path to the Exit):**  
>    Using shortest-path algorithms across our registry of 50+ known exchanges and bridges, TRACE-X pinpoints the exact destination exchange, categorizing attribution into calibrated confidence levels: Confirmed, High Confidence, or Probable.
> 
> 5. **AI Investigation Assistant:**  
>    An evidence-grounded AI copilot that synthesizes the graph findings, explains complex patterns in plain English, and drafts case summaries—strictly locked to on-chain evidence with zero hallucinations.
> 
> *(5-Minute Trim Cue: If running behind, summarize points 2–5: "Our engine detects laundering patterns, calculates 12-factor explainable risk, pinpoints the destination exchange via shortest path, and provides an evidence-grounded AI assistant.")*

---

### Minute 4:10 – 5:15 | Technical Architecture & Implementation
**[SLIDE 3: TECHNICAL APPROACH]**

> "Moving to Slide 3, here is our Technical Architecture:
> 
> - **Data Ingestion:** We interface with Alchemy and Infura EVM RPC nodes, extracting and normalizing raw blockchain payloads, token decimals, and ERC-20 transfers.
> - **Dual-Database Design:** Relational application state, case files, RBAC, and audit logs reside in **PostgreSQL**. The complex transaction graph resides in **Neo4j**, enabling high-speed Cypher queries for deep graph traversal.
> - **Asynchronous Processing:** Built on **FastAPI (Python)**, utilizing **Redis and Celery** background workers so intensive multi-hop graph crawls never freeze the user interface.
> - **Frontend Experience:** Built with **Next.js 14 and React Flow**, delivering high-performance, interactive network visualization on both desktop and responsive mobile interfaces.
> - **Dual-Mode AI Engine:** Supports a live LLM mode for dynamic natural language queries, as well as a deterministic rule-based mode for completely air-gapped or offline police deployments."

---

### Minute 5:15 – 6:00 | Feasibility & Overcoming Real-World Challenges
**[SLIDE 4: FEASIBILITY AND VIABILITY]**

> "On Slide 4, we address how TRACE-X handles real-world operational challenges:
> 
> - **Handling Massive Data Volume:** We use value-floor filtering to eliminate dust transactions, combined with Redis caching and indexed Neo4j schemas to keep graph analysis fast.
> - **Attribution Accuracy:** To prevent serving wrongful notices, we distinguish between verified clusters and unverified hops using calibrated confidence scoring.
> - **Eliminating AI Hallucinations:** Our AI is mathematically grounded. It is strictly constrained to the ingested case subgraph and must cite verified transaction hashes for every claim.
> - **Security & Legal Admissibility:** With role-based access control (Analyst, Supervisor, Admin) and tamper-evident audit logs, every step of the investigation preserves the chain of custody for court."

---

### Minute 6:00 – 6:45 | Impact, Benefits & Conclusion
**[SLIDE 5: IMPACT AND BENEFITS]**

> "To conclude on Slide 5—the real-world impact of TRACE-X:
> 
> - **Speed:** We compress a **4-day manual investigation into under 3 minutes**.
> - **Actionable Legal Output:** TRACE-X generates ready-to-serve statutory notice templates (like Section 91 CrPC) complete with transaction hashes, timestamps, and destination exchange details so officers can freeze accounts during that critical Golden Period.
> - **Global Alignment:** Our platform directly supports **UN Sustainable Development Goals 16 (Peace, Justice & Strong Institutions)**, **8**, and **9** by shutting down cybercrime financial infrastructure.
> 
> Our workflow is simple:  
> **TRACE. VISUALIZE. DETECT. UNDERSTAND. REPORT.**  
> 
> Thank you, and we are now open for your questions."
