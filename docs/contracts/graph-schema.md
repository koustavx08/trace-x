# Neo4j Graph Schema

> **Status:** Baseline reference (pre-parallel-merge). Derived from `apps/api/src/graph/models/__init__.py`,
> `apps/api/src/graph/queries.py`, `apps/api/src/graph/repository.py`, `apps/api/src/graph/client.py`, and the graph
> API router `apps/api/src/api/v1/graph.py`.

## Node types (dataclasses in `graph/models/__init__.py`)

### `Wallet` node → `GraphWallet`

```python
address: str
chain: str
label: str | None
risk_score: float = 0.0
first_seen / last_seen: datetime | None
total_sent / total_received: int = 0
tx_count: int = 0
metadata: dict
entity_name: str | None
entity_type: EntityType | None
entity_confidence: ConfidenceLevel = UNKNOWN
```
Node id convention: `f"Wallet:{chain}:{address.lower()}"`.

### `Transaction` node → `GraphTransaction`

```python
tx_hash, chain, block_number, timestamp
from_address, to_address, value, value_usd
token_address, token_symbol, method
gas_used, gas_price
is_suspicious: bool
metadata: dict
```
Node id: `f"Transaction:{chain}:{tx_hash.lower()}"`.

### `Entity` node → `GraphEntity`

```python
name: str
entity_type: EntityType
address: str
chain: str
confidence: ConfidenceLevel = UNKNOWN
source: str = "manual"
tags: list[str]
metadata: dict
first_seen / last_verified: datetime | None
```
Node id: `f"Entity:{chain}:{address.lower()}"`.

### `GraphPath` (query result, not a persisted node)

```python
nodes: list[str]           # node ids in path order
edges: list[dict]
total_value: float
length: int
confidence: ConfidenceLevel
endpoint_entity: GraphEntity | None
```

## Enums

```python
class EntityType(str, Enum):
    EXCHANGE, MIXER, BRIDGE, DEFI, SANCTIONED, GAMBLING, DARKNET, UNKNOWN

class ConfidenceLevel(str, Enum):
    CONFIRMED, HIGH_CONFIDENCE, PROBABLE, UNKNOWN
```
(These are duplicated near-identically in `src/schemas/__init__.py`, `src/ai/schemas.py`, and `src/analytics/*.py` —
each module defines its own copy rather than importing a single shared enum. Not unified as of baseline.)

## Relationships (inferred from Cypher in `graph/queries.py` / `graph/repository.py`)

| Relationship | Direction | Used by |
|---|---|---|
| `SENT` | `(Wallet)-[:SENT]->(Transaction)` | peel-chain detection, rapid-movement detection, temporal flow |
| `RECEIVED` | `(Transaction)-[:RECEIVED]->(Wallet)` | mixer/VASP path traversal (`SENT|RECEIVED` relationship type union) |
| `BELONGS_TO` | `(Wallet)-[:BELONGS_TO]->(Entity)` | entity exposure queries |

## Key Cypher-backed queries (`GraphQueries` in `graph/queries.py`)

| Method | Purpose | Notes |
|---|---|---|
| `shortest_path_to_vasp` | Dijkstra shortest path from a wallet to a `confidence IN [CONFIRMED, HIGH_CONFIDENCE]` exchange entity | Requires the **APOC** plugin (`apoc.algo.dijkstra`) — `NEO4J_PLUGINS` in `docker-compose.prod.yml` includes `apoc` and `graph-data-science` |
| `find_mixer_interactions` | Same dijkstra approach targeting `entity_type: 'mixer'` | |
| `detect_peel_chains` | Chained `SENT` paths ≥ `min_hops` where every hop exceeds `min_value_eth`, from wallets with `tx_count > 10` | |
| `detect_round_amount_patterns` | Repeated whole-ETH-value transactions from the same origin within a time window | |
| `detect_rapid_movement` | 3-hop `w1→t1→w2→t2→w3` sequences under `max_time_between_txs_seconds` | |
| `get_wallet_centrality` | `pagerank` / `betweenness` via **Graph Data Science (GDS)** plugin, or naive `tx_count` fallback | Requires a named GDS graph projection `'wallet-graph'` — no code in the baseline tree was found that actually creates this projection; if it's never created, the `pagerank`/`betweenness` branches will error at query time. Flag for verification. |
| `get_temporal_flow` | Bucketed (hour/day/week) sent-transaction volume for a wallet | |
| `get_entity_exposure` | Aggregate wallet/tx exposure to a given entity | |

## Frontend consumption

`apps/web/src/lib/api.ts` defines `GraphNode`/`GraphEdge`/`SubgraphResponse` client-side types that are a *simplified*
projection of the above (flat `id/type/address/label/...` shape), not a 1:1 mirror of the dataclasses above. Per
`docs/FEATURE_REALITY_MATRIX.md`, the `/graph` page was MOCKED (placeholder data) as of the last audit — WS6 is
expected to wire it to `graphApi.getSubgraph` for real; re-verify the actual node/edge shape once merged, since WS6's
task list explicitly includes "shape them in `getSubgraph`'s response mapping."
