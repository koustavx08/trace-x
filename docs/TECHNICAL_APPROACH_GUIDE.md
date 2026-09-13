# TRACE-X: Technical Approach & Architecture Guide (Slide 3)

> **Context:** Complete technical defense and presentation companion for **Slide 3 (Technical Approach)** for SIH 2026 Problem Statement **SIH26183** (Team **ZERO_DAY**).

---

# PART 1: Tech Stack Breakdown (Layman vs. Technical)

---

### 1. Frontend: Next.js 14 & React Flow
* **In Layman Terms:**  
  Think of this as the **dashboard and windshield of a police patrol car**. It is the visual screen where the investigating officer inputs the suspect's wallet, clicks buttons, and views an interactive visual crime map where wallets are circles and money transfers are arrows that can be zoomed, dragged, and inspected.
* **In Technical Terms:**  
  * **Next.js 14 (App Router):** Server-side rendered React framework providing optimized page routing, fast initial page loads, and TypeScript type-safety.
  * **React Flow:** A specialized node-based graph rendering library used in the browser. It converts raw graph data into interactive, draggable nodes (Wallets/Exchanges) and directed edges (Transactions) using Dagre layout algorithms.
* **Why We Used It:**  
  Standard HTML tables cannot display 5-hop laundering trees. React Flow makes multi-hop money flow instantly understandable to a non-technical judge or police officer in seconds.

---

### 2. Backend API: Python 3.11 & FastAPI
* **In Layman Terms:**  
  Think of FastAPI as the **brain and central traffic police officer** of the whole system. When you click a button on the screen, FastAPI receives the command, checks who you are, asks the blockchain for data, instructs the database to save it, and hands the result back to the screen.
* **In Technical Terms:**  
  An asynchronous, high-performance Python web framework utilizing Starlette and Pydantic. It provides non-blocking I/O (`async`/`await`), automatic OpenAPI/Swagger documentation, and native dependency injection for authentication and database sessions.
* **Why We Used It:**  
  Blockchain data analysis involves heavy data transformation and graph math. Python is the gold standard for data science and forensics, and FastAPI is one of the fastest Python web servers in existence (on par with NodeJS and Go).

---

### 3. Relational Storage: PostgreSQL
* **In Layman Terms:**  
  Think of PostgreSQL as the **locked, fireproof filing cabinet in the police station**. It stores standard structured files: officer login passwords, official case numbers, complaint dates, victim names, and statutory audit logs that must never be lost.
* **In Technical Terms:**  
  An enterprise-grade Relational Database Management System (RDBMS) providing strict **ACID compliance** (Atomicity, Consistency, Isolation, Durability). Managed via SQLAlchemy ORM and Alembic migrations.
* **Why We Used It:**  
  You cannot store legal court evidence and user accounts in a loose, unstructured database. PostgreSQL ensures that case files, timestamps, and investigator access records can never get corrupted.

---

### 4. Graph Database: Neo4j
* **In Layman Terms:**  
  Imagine a detective’s pin-board with red strings connecting suspects, phone calls, and crime scenes. **Neo4j is a digital version of that pin-board.** Unlike traditional databases that store data in flat Excel-like rows, Neo4j stores data as **Nodes (Wallets)** connected by **Edges (Transactions)**.
* **In Technical Terms:**  
  A native labeled property graph database that utilizes the **Cypher query language** and **APOC (Awesome Procedures on Cypher)**. Relationships are stored as first-class physical pointers in memory (index-free adjacency).
* **Why We Used It:**  
  To trace money 5 hops deep in a regular SQL database, you have to write 5 complex, recursive `JOIN` queries that take 30 to 60 seconds and can crash the database. **In Neo4j, traversing 5 hops takes less than 20 milliseconds** because it simply follows pointers from one node to the next.

> **💡 The #1 Judge Question: *"Why did you use BOTH PostgreSQL and Neo4j?"***  
> **Your Answer:** *"We use a **Hybrid Storage Architecture**. PostgreSQL handles relational administrative data where ACID transactional integrity matters (cases, users, audit logs). Neo4j handles fund flow graph topology where millisecond multi-hop traversal and Dijkstra shortest-path algorithms are required. Each database does what it was born to do."*

---

### 5. Background Queue & Cache: Redis + Celery
* **In Layman Terms:**  
  Imagine ordering at a restaurant. The cashier takes your order in 2 seconds, hands you a token, and tells you to take a seat while the kitchen cooks the meal. **FastAPI is the cashier; Celery is the kitchen chef; Redis is the counter where orders wait.**
* **In Technical Terms:**  
  * **Redis:** An in-memory key-value data store used as a high-speed cache and message broker.
  * **Celery:** An asynchronous distributed task queue that executes heavy background jobs.
* **Why We Used It:**  
  Crawling 10 hops of blockchain data can take 15–20 seconds. If FastAPI did that on the main thread, the entire browser screen would freeze. With Celery and Redis, the crawling runs silently in the background while the UI stays smooth and responsive.

---

### 6. Blockchain Ingestion: Alchemy & Infura EVM RPC Nodes
* **In Layman Terms:**  
  Think of this as the **telephone wire connecting our software directly to the Ethereum and Polygon blockchains**. It asks the blockchain: *"Tell me every single transaction that left this suspect wallet."*
* **In Technical Terms:**  
  Abstracted via a Factory Pattern (`ProviderFactory`). Interacts with EVM JSON-RPC nodes and the **Alchemy Asset Transfers API** to retrieve raw transactions, ERC-20 token logs (USDT, USDC), gas fees, and block timestamps, normalizing them into clean Pydantic schemas.
* **Why We Used It:**  
  It abstracts away the low-level complexities of raw hexadecimal blockchain data and handles multiple chains (Ethereum Mainnet, Polygon) through a single unified interface.

---

### 7. Dual-Mode AI Engine (Claude 3.5 / Gemini / Rule-Based Fallback)
* **In Layman Terms:**  
  Think of this as an **expert cybercrime assistant sitting next to the officer**. It reads the complex graph and explains it in plain English: *"This money was split into 4 burner wallets and reached Binance 12 minutes ago."*
* **In Technical Terms:**  
  A **Retrieval-Constrained Generation (RCG)** engine. The AI prompt is strictly bounded by the mathematical graph output. If internet access is cut off (an air-gapped forensic lab), it automatically falls back to a **Deterministic Rule-Based Generator** so the platform never stops working.
* **Why We Used It:**  
  Generic AI (like ChatGPT) hallucinates fake transaction hashes. Our AI is mathematically locked: it can only cite transaction hashes that actually exist in the Neo4j database.

---

### 8. Containerization: Docker & Docker Compose
* **In Layman Terms:**  
  Think of Docker as shipping a **pre-assembled, sealed police crime lab in a single shipping container**.
* **In Technical Terms:**  
  Containerizes the FastAPI API, PostgreSQL, Neo4j, Redis, Celery worker, and Next.js frontend into isolated, orchestrated microservices defined in `docker-compose.yml`.
* **Why We Used It:**  
  A police IT department doesn't want to spend 3 days installing Python, Neo4j, and databases manually. With Docker, they type `docker compose up -d` and the entire platform spins up in 60 seconds on any laptop or server.

---

# PART 2: The End-to-End Workflow (What Happens First to Last)

Here is the exact step-by-step journey of an investigation through the system:

```
[1. Case Creation] ──> [2. Ingestion & Normalization] ──> [3. Neo4j Graph Construction]
         │
         ▼
[4. Pattern & Risk Engine] ──> [5. VASP Dijkstra Attribution] ──> [6. AI Court Report]
```

### Step 1: Report & Case Creation (Frontend $\to$ FastAPI $\to$ PostgreSQL)
1. The investigator logs into the **Next.js** web portal (authenticated via JWT and RBAC).
2. The officer enters the victim-reported wallet address (e.g., `0x71A...`), selects the blockchain (Ethereum), and clicks **Start Investigation**.
3. **FastAPI** validates the address using **EIP-55 checksum standards** to ensure it’s a valid cryptographic format, creates a formal Case ID in **PostgreSQL**, and logs an immutable audit trail.

---

### Step 2: Asynchronous Blockchain Ingestion (Celery $\to$ Alchemy/Infura)
1. FastAPI hands the task off to **Celery** via **Redis**.
2. Celery calls the **Alchemy Asset Transfers API** to fetch all historical transactions associated with the suspect wallet.
3. The raw hexadecimal outputs are **normalized**: converting Wei into readable ETH, adjusting decimals for stablecoins (USDT/USDC), and parsing timestamps.
4. If multi-hop is enabled, the engine executes a **Breadth-First Search (BFS)**, fetching outgoing transactions for every child recipient wallet up to $N$ hops deep.

---

### Step 3: Graph Materialization (Neo4j APOC Cypher)
1. The Celery worker pushes the normalized data into **Neo4j**.
2. Neo4j creates labeled nodes:
   * `(:Wallet {address: "0x..."})`
   * `(:Transaction {hash: "0x...", value: 5.0, timestamp: "..."})`
   * `(:Entity {name: "Binance", type: "exchange"})`
3. It creates directional relationships:
   * `(:Wallet)-[:SENT]->(:Transaction)-[:RECEIVED]->(:Wallet)`

---

### Step 4: Pattern Detection & 12-Factor Risk Scoring (Python Analytics Core)
1. The **Risk Engine** runs automated Cypher graph queries across the freshly materialized subgraph.
2. It evaluates the **12 behavioral factors**:
   * *Did funds enter a mixer?* $\to$ `MIXER_INTERACTION`
   * *Were transactions split sequentially?* $\to$ `PEEL_CHAIN`
   * *Did 3 transfers happen within 300 seconds?* $\to$ `RAPID_MOVEMENT`
   * *Does an address match OFAC sanctions?* $\to$ `SANCTIONS_HIT`
3. The engine computes the **Normalized Weighted Score** and applies the **10% co-occurrence compounding multiplier**, outputting a final score between 0 and 100 with clear evidence notes.

---

### Step 5: VASP Shortest-Path Attribution (Dijkstra Algorithm)
1. The engine checks if any node in the graph matches our **Entity Registry** of 50+ known exchanges (Binance, Kraken, CoinDCX, etc.).
2. It executes **Dijkstra’s Shortest-Path Algorithm** in Neo4j to find the fastest, minimal-hop route from the suspect wallet to the exchange.
3. It calculates a **Calibrated Confidence Level**:
   * Direct transfer $\to$ **`CONFIRMED`** ($C \ge 0.85$)
   * 2 hops with high value preservation $\to$ **`HIGH_CONFIDENCE`** ($0.70 \le C < 0.85$)
   * 4+ hops or diluted funds $\to$ **`PROBABLE`** ($0.50 \le C < 0.70$)

---

### Step 6: Grounded AI Synthesis & Report Generation (AI Engine $\to$ PDF Locker)
1. The extracted graph path, risk breakdown, and attribution proof are packaged into a structured JSON payload and handed to the **AI Copilot**.
2. The AI generates an executive summary and explains the laundering scheme in plain English—strictly citing verified transaction hashes.
3. With one click, the system compiles a formal **Section 91 CrPC / Section 65B Indian Evidence Act compliant PDF report**.
4. The report includes:
   * The destination exchange name and unique deposit address.
   * Exact transaction hashes, amounts, and timestamps.
   * Pre-drafted statutory legal freezing notice ready to be signed and emailed to the crypto exchange compliance desk.
