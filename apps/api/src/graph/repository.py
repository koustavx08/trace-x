import json
from typing import Any

import structlog

from .analytics import detect_communities, load_wallet_graph
from .client import Neo4jClient
from .models import (
    ConfidenceLevel,
    EntityType,
    GraphEntity,
    GraphPath,
    GraphTransaction,
    GraphWallet,
)

logger = structlog.get_logger(__name__)


def _as_float(value: Any) -> float | None:
    """Coerce a numeric to a plain float for Neo4j, preserving None.

    SQLAlchemy `Numeric` columns (Transaction.value_usd, Wallet.risk_score)
    come back as `decimal.Decimal`, which the Bolt driver refuses with
    "Values of type <class 'decimal.Decimal'> are not supported" -- that killed
    graph_sync_task for any transaction carrying a USD value. GraphTransaction
    already declares these as `float | None`; this enforces it at the boundary
    so every caller is covered.
    """
    return None if value is None else float(value)


def _dump_metadata(metadata: dict[str, Any] | None) -> str | None:
    """Serialize a metadata dict for storage as a Neo4j property.

    Neo4j property values must be primitives or arrays of primitives -- handing
    it a nested map raises `Neo.ClientError.Statement.TypeError`, so any node
    carrying non-empty metadata failed to write at all. Store it as a JSON
    string and decode on read (see `_load_metadata`).
    """
    if not metadata:
        return None
    return json.dumps(metadata, default=str)


def _load_metadata(value: Any) -> dict[str, Any]:
    """Inverse of `_dump_metadata`, tolerant of pre-existing/legacy values."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            logger.warning("graph_metadata_decode_failed", value=value[:200])
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


class GraphRepository:
    def __init__(self):
        self._client = Neo4jClient

    async def upsert_wallet(self, wallet: GraphWallet) -> GraphWallet:
        query = """
        MERGE (w:Wallet {address: $address, chain: $chain})
        ON CREATE SET
            w.created_at = datetime(),
            w.label = $label,
            w.risk_score = $risk_score,
            w.first_seen = $first_seen,
            w.last_seen = $last_seen,
            w.total_sent = $total_sent,
            w.total_received = $total_received,
            w.tx_count = $tx_count,
            w.metadata = $metadata,
            w.entity_name = $entity_name,
            w.entity_type = $entity_type,
            w.entity_confidence = $entity_confidence
        ON MATCH SET
            w.label = COALESCE($label, w.label),
            w.risk_score = $risk_score,
            w.last_seen = $last_seen,
            w.total_sent = w.total_sent + $total_sent,
            w.total_received = w.total_received + $total_received,
            w.tx_count = w.tx_count + $tx_count,
            w.metadata = COALESCE($metadata, w.metadata),
            w.entity_name = COALESCE($entity_name, w.entity_name),
            w.entity_type = COALESCE($entity_type, w.entity_type),
            w.entity_confidence = COALESCE($entity_confidence, w.entity_confidence),
            w.updated_at = datetime()
        RETURN w
        """
        params = {
            "address": wallet.address.lower(),
            "chain": wallet.chain,
            "label": wallet.label,
            "risk_score": _as_float(wallet.risk_score),
            "first_seen": wallet.first_seen,
            "last_seen": wallet.last_seen,
            "total_sent": wallet.total_sent,
            "total_received": wallet.total_received,
            "tx_count": wallet.tx_count,
            "metadata": _dump_metadata(wallet.metadata),
            "entity_name": wallet.entity_name,
            "entity_type": wallet.entity_type.value if wallet.entity_type else None,
            "entity_confidence": wallet.entity_confidence.value,
        }
        await self._client.execute_write(query, params)
        return wallet

    async def update_wallet_risk_score(self, address: str, chain: str, risk_score: float) -> None:
        query = """
        MATCH (w:Wallet)
        WHERE toLower(w.address) = toLower($address) AND toLower(w.chain) = toLower($chain)
        SET w.risk_score = $risk_score,
            w.updated_at = datetime()
        RETURN count(w) AS updated
        """
        await self._client.execute_write(
            query,
            {
                "address": address.lower(),
                "chain": chain,
                "risk_score": _as_float(risk_score),
            },
        )

    async def batch_update_wallet_risk_scores(self, updates: list[dict[str, Any]]) -> None:
        query = """
        UNWIND $updates AS item
        MATCH (w:Wallet)
        WHERE toLower(w.address) = toLower(item.address)
        SET w.risk_score = item.risk_score,
            w.updated_at = datetime()
        """
        cleaned = [
            {
                "address": u["address"].lower(),
                "risk_score": _as_float(u["risk_score"]),
            }
            for u in updates
        ]
        await self._client.execute_write(query, {"updates": cleaned})

    async def upsert_transaction(self, tx: GraphTransaction) -> GraphTransaction:
        query = """
        MERGE (t:Transaction {tx_hash: $tx_hash, chain: $chain})
        ON CREATE SET
            t.block_number = $block_number,
            t.timestamp = $timestamp,
            t.from_address = $from_address,
            t.to_address = $to_address,
            t.value = $value,
            t.value_usd = $value_usd,
            t.token_address = $token_address,
            t.token_symbol = $token_symbol,
            t.method = $method,
            t.gas_used = $gas_used,
            t.gas_price = $gas_price,
            t.is_suspicious = $is_suspicious,
            t.metadata = $metadata,
            t.created_at = datetime()
        ON MATCH SET
            t.value_usd = COALESCE($value_usd, t.value_usd),
            t.is_suspicious = $is_suspicious,
            t.metadata = COALESCE($metadata, t.metadata)
        RETURN t
        """
        params = {
            "tx_hash": tx.tx_hash.lower(),
            "chain": tx.chain,
            "block_number": tx.block_number,
            "timestamp": tx.timestamp,
            "from_address": tx.from_address.lower(),
            "to_address": tx.to_address.lower(),
            "value": tx.value,
            "value_usd": _as_float(tx.value_usd),
            "token_address": tx.token_address.lower() if tx.token_address else None,
            "token_symbol": tx.token_symbol,
            "method": tx.method,
            "gas_used": tx.gas_used,
            "gas_price": tx.gas_price,
            "is_suspicious": tx.is_suspicious,
            "metadata": _dump_metadata(tx.metadata),
        }
        await self._client.execute_write(query, params)
        return tx

    async def link_wallet_transaction(
        self, wallet_address: str, chain: str, tx_hash: str, direction: str
    ) -> None:
        if direction == "sent":
            query = """
            MATCH (w:Wallet {address: $address, chain: $chain})
            MATCH (t:Transaction {tx_hash: $tx_hash, chain: $chain})
            MERGE (w)-[:SENT {timestamp: datetime()}]->(t)
            """
        else:
            query = """
            MATCH (w:Wallet {address: $address, chain: $chain})
            MATCH (t:Transaction {tx_hash: $tx_hash, chain: $chain})
            MERGE (t)-[:RECEIVED {timestamp: datetime()}]->(w)
            """
        await self._client.execute_write(
            query,
            {
                "address": wallet_address.lower(),
                "chain": chain,
                "tx_hash": tx_hash.lower(),
            },
        )

    async def upsert_entity(self, entity: GraphEntity) -> GraphEntity:
        query = """
        MERGE (e:Entity {address: $address, chain: $chain})
        ON CREATE SET
            e.name = $name,
            e.entity_type = $entity_type,
            e.confidence = $confidence,
            e.source = $source,
            e.tags = $tags,
            e.metadata = $metadata,
            e.first_seen = $first_seen,
            e.last_verified = $last_verified,
            e.created_at = datetime()
        ON MATCH SET
            e.name = $name,
            e.entity_type = $entity_type,
            e.confidence = CASE WHEN $confidence > e.confidence THEN $confidence ELSE e.confidence END,
            e.source = COALESCE($source, e.source),
            e.tags = CASE WHEN size($tags) > 0 THEN $tags ELSE e.tags END,
            e.metadata = COALESCE($metadata, e.metadata),
            e.last_verified = $last_verified,
            e.updated_at = datetime()
        RETURN e
        """
        params = {
            "address": entity.address.lower(),
            "chain": entity.chain,
            "name": entity.name,
            "entity_type": entity.entity_type.value,
            "confidence": entity.confidence.value,
            "source": entity.source,
            "tags": entity.tags,
            "metadata": _dump_metadata(entity.metadata),
            "first_seen": entity.first_seen,
            "last_verified": entity.last_verified,
        }
        await self._client.execute_write(query, params)
        return entity

    async def link_wallet_entity(
        self, wallet_address: str, chain: str, entity_address: str
    ) -> None:
        query = """
        MATCH (w:Wallet {address: $wallet_address, chain: $chain})
        MATCH (e:Entity {address: $entity_address, chain: $chain})
        MERGE (w)-[:BELONGS_TO {confidence: e.confidence, linked_at: datetime()}]->(e)
        """
        await self._client.execute_write(
            query,
            {
                "wallet_address": wallet_address.lower(),
                "chain": chain,
                "entity_address": entity_address.lower(),
            },
        )

    async def get_wallet(self, address: str, chain: str) -> GraphWallet | None:
        query = """
        MATCH (w:Wallet {address: $address, chain: $chain})
        RETURN w
        """
        result = await self._client.execute_query(
            query, {"address": address.lower(), "chain": chain}
        )
        if not result:
            return None
        record = result[0]
        w = record["w"]
        return GraphWallet(
            address=w["address"],
            chain=w["chain"],
            label=w.get("label"),
            risk_score=w.get("risk_score", 0.0),
            first_seen=w.get("first_seen"),
            last_seen=w.get("last_seen"),
            total_sent=w.get("total_sent", 0),
            total_received=w.get("total_received", 0),
            tx_count=w.get("tx_count", 0),
            metadata=_load_metadata(w.get("metadata")),
            entity_name=w.get("entity_name"),
            entity_type=EntityType(w["entity_type"]) if w.get("entity_type") else None,
            entity_confidence=ConfidenceLevel(w["entity_confidence"])
            if w.get("entity_confidence")
            else ConfidenceLevel.UNKNOWN,
        )

    async def get_wallet_neighbors(
        self, address: str, chain: str, depth: int = 1, limit: int = 100
    ) -> list[GraphWallet]:
        query = f"""
        MATCH (w:Wallet {{address: $address, chain: $chain}})
        CALL apoc.path.subgraphNodes(w, {{
            maxLevel: {depth},
            relationshipFilter: "SENT|RECEIVED"
        }}) YIELD node
        WHERE node:Wallet
        RETURN node
        LIMIT $limit
        """
        result = await self._client.execute_query(
            query, {"address": address.lower(), "chain": chain, "limit": limit}
        )
        wallets = []
        for record in result:
            n = record["node"]
            wallets.append(
                GraphWallet(
                    address=n["address"],
                    chain=n["chain"],
                    label=n.get("label"),
                    risk_score=n.get("risk_score", 0.0),
                    entity_name=n.get("entity_name"),
                    entity_type=EntityType(n["entity_type"]) if n.get("entity_type") else None,
                    entity_confidence=ConfidenceLevel(n["entity_confidence"])
                    if n.get("entity_confidence")
                    else ConfidenceLevel.UNKNOWN,
                )
            )
        return wallets

    async def find_paths_to_entities(
        self,
        start_address: str,
        chain: str,
        entity_types: list[EntityType] | None = None,
        max_depth: int = 6,
        min_confidence: ConfidenceLevel = ConfidenceLevel.PROBABLE,
        limit: int = 10,
    ) -> list[GraphPath]:
        entity_filter = ""
        if entity_types:
            quoted_types = ", ".join(f'"{t.value}"' for t in entity_types)
            # The Entity node is bound as `end` in the query below, not `e`.
            # Filtering on `e.entity_type` produced "Variable `e` not defined",
            # so passing any entity_types at all made this a CypherSyntaxError.
            entity_filter = f"AND end.entity_type IN [{quoted_types}]"

        confidence_order = {
            ConfidenceLevel.CONFIRMED: 4,
            ConfidenceLevel.HIGH_CONFIDENCE: 3,
            ConfidenceLevel.PROBABLE: 2,
            ConfidenceLevel.UNKNOWN: 1,
        }
        min_conf_val = confidence_order[min_confidence]

        query = f"""
        MATCH (start:Wallet {{address: $start_address, chain: $chain}})
        MATCH (end:Entity)
        WHERE end.chain = $chain {entity_filter}
        AND CASE end.confidence
            WHEN 'CONFIRMED' THEN 4
            WHEN 'HIGH_CONFIDENCE' THEN 3
            WHEN 'PROBABLE' THEN 2
            ELSE 1
        END >= $min_conf
        // Wallets connect to each other through Transaction nodes (SENT/RECEIVED),
        // but an Entity hangs off its wallet by BELONGS_TO. Traversing only
        // SENT|RECEIVED therefore can never *terminate* on an :Entity, so this
        // query returned zero paths for every input and attribution was always
        // empty. BELONGS_TO is the final hop onto the entity.
        //
        // The 5th argument is dijkstra's defaultWeight. SENT/RECEIVED/BELONGS_TO
        // carry no 'value' property, and APOC's default for a missing weight is
        // NaN -- which poisons the cumulative path weight and drops the row.
        // 1.0 makes the weight a plain hop count.
        CALL apoc.algo.dijkstra(start, end, 'SENT|RECEIVED|BELONGS_TO', 'value', 1.0) YIELD path, weight
        // max_depth is a count of WALLET hops (that is what callers pass and what
        // GraphPath.length reports, since Transaction nodes are skipped when the
        // path is rendered). Neo4j's length(path) counts RELATIONSHIPS, and one
        // wallet-to-wallet hop is two of them (SENT then RECEIVED) plus the one
        // terminal BELONGS_TO onto the entity. Comparing the two directly
        // rejected paths well inside the requested depth.
        WHERE length(path) <= $max_depth * 2 + 1
        RETURN path, weight, end
        // Ascending: the caller wants the *nearest* VASP. With DESC the LIMIT
        // kept the furthest entities and could cut the closest one entirely.
        ORDER BY weight ASC
        LIMIT $limit
        """
        result = await self._client.execute_query(
            query,
            {
                "start_address": start_address.lower(),
                "chain": chain,
                "max_depth": max_depth,
                "min_conf": min_conf_val,
                "limit": limit,
            },
        )

        paths = []
        for record in result:
            path = record["path"]
            weight = record["weight"]
            end = record["end"]

            nodes = []
            edges = []
            for i, node in enumerate(path.nodes):
                if "Wallet" in node.labels:
                    nodes.append(f"Wallet:{node['chain']}:{node['address']}")
                elif "Entity" in node.labels:
                    nodes.append(f"Entity:{node['chain']}:{node['address']}")
                if i > 0:
                    prev = path.nodes[i - 1]
                    rel = path.relationships[i - 1]
                    edges.append(
                        {
                            "from": f"Wallet:{prev['chain']}:{prev['address']}"
                            if "Wallet" in prev.labels
                            else f"Entity:{prev['chain']}:{prev['address']}",
                            "to": f"Wallet:{node['chain']}:{node['address']}"
                            if "Wallet" in node.labels
                            else f"Entity:{node['chain']}:{node['address']}",
                            "value": rel.get("value", 0),
                            "tx_hash": rel.get("tx_hash", ""),
                        }
                    )

            paths.append(
                GraphPath(
                    nodes=nodes,
                    edges=edges,
                    total_value=weight,
                    length=len(nodes) - 1,
                    confidence=ConfidenceLevel(end["confidence"]),
                    endpoint_entity=GraphEntity(
                        name=end["name"],
                        entity_type=EntityType(end["entity_type"]),
                        address=end["address"],
                        chain=end["chain"],
                        confidence=ConfidenceLevel(end["confidence"]),
                        source=end.get("source", "unknown"),
                    ),
                )
            )
        return paths

    async def get_subgraph(
        self, addresses: list[str], chain: str, depth: int = 2
    ) -> dict[str, Any]:
        addr_list = [a.lower() for a in addresses]
        query = """
        MATCH (w:Wallet)
        WHERE w.address IN $addresses AND w.chain = $chain
        CALL apoc.path.subgraphAll(w, {
            maxLevel: $depth,
            relationshipFilter: "SENT|RECEIVED|BELONGS_TO"
        }) YIELD nodes, relationships
        RETURN nodes, relationships
        """
        result = await self._client.execute_query(
            query,
            {
                "addresses": addr_list,
                "chain": chain,
                "depth": depth,
            },
        )

        nodes = []
        edges = []
        node_id_map = {}
        for record in result:
            for node in record["nodes"]:
                if "Wallet" in node.labels:
                    custom_id = f"Wallet:{node['chain']}:{node['address']}"
                    node_id_map[node.id] = custom_id
                    nodes.append(
                        {
                            "id": custom_id,
                            "type": "wallet",
                            "address": node["address"],
                            "chain": node["chain"],
                            "label": node.get("label"),
                            "risk_score": node.get("risk_score", 0),
                            "entity_name": node.get("entity_name"),
                            "entity_confidence": node.get("entity_confidence"),
                        }
                    )
                elif "Entity" in node.labels:
                    custom_id = f"Entity:{node['chain']}:{node['address']}"
                    node_id_map[node.id] = custom_id
                    nodes.append(
                        {
                            "id": custom_id,
                            "type": "entity",
                            "name": node["name"],
                            "entity_type": node["entity_type"],
                            "address": node["address"],
                            "chain": node["chain"],
                            "confidence": node["confidence"],
                        }
                    )
                elif "Transaction" in node.labels:
                    custom_id = f"Transaction:{node['chain']}:{node['tx_hash']}"
                    node_id_map[node.id] = custom_id
                    nodes.append(
                        {
                            "id": custom_id,
                            "type": "transaction",
                            "tx_hash": node["tx_hash"],
                            "value": node.get("value"),
                            "value_usd": node.get("value_usd"),
                        }
                    )

            for rel in record["relationships"]:
                start_id = node_id_map.get(rel.start_node.id, str(rel.start_node.id))
                end_id = node_id_map.get(rel.end_node.id, str(rel.end_node.id))
                edges.append(
                    {
                        "from": start_id,
                        "to": end_id,
                        "type": rel.type,
                        "properties": dict(rel),
                    }
                )

        return {"nodes": nodes, "edges": edges}

    async def detect_clusters(self, chain: str, min_cluster_size: int = 3) -> list[dict[str, Any]]:
        """Group wallets that move funds among themselves into clusters.

        Computed in-process from a Cypher projection (see `graph.analytics`).
        The previous implementation called `algo.louvain.stream`, the Neo4j 3.x
        procedure namespace, which has not existed for several major versions
        and is not what the Graph Data Science library provides either -- every
        request failed with ProcedureNotFound.
        """
        graph, attributes = await load_wallet_graph(self._client, chain)
        return detect_communities(graph, attributes, min_cluster_size)

    async def get_wallet_stats(self, address: str, chain: str) -> dict[str, Any]:
        query = """
        MATCH (w:Wallet {address: $address, chain: $chain})
        OPTIONAL MATCH (w)-[:SENT]->(t:Transaction)
        OPTIONAL MATCH (t2:Transaction)-[:RECEIVED]->(w)
        RETURN w,
               count(DISTINCT t) as sent_count,
               count(DISTINCT t2) as received_count,
               sum(CASE WHEN t.value IS NOT NULL THEN toFloat(t.value) ELSE 0 END) as total_sent,
               sum(CASE WHEN t2.value IS NOT NULL THEN toFloat(t2.value) ELSE 0 END) as total_received
        """
        result = await self._client.execute_query(
            query, {"address": address.lower(), "chain": chain}
        )
        if not result:
            return {}
        record = result[0]
        w = record["w"]
        return {
            "address": w["address"],
            "chain": w["chain"],
            "label": w.get("label"),
            "risk_score": w.get("risk_score", 0),
            "tx_count": w.get("tx_count", 0),
            "sent_count": record["sent_count"],
            "received_count": record["received_count"],
            "total_sent": record["total_sent"],
            "total_received": record["total_received"],
            "entity_name": w.get("entity_name"),
            "entity_type": w.get("entity_type"),
            "entity_confidence": w.get("entity_confidence"),
        }


graph_repository = GraphRepository()
