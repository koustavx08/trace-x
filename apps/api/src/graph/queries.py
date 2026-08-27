from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import structlog

from .client import Neo4jClient
from .models import ConfidenceLevel, EntityType

logger = structlog.get_logger(__name__)


class GraphQueries:
    def __init__(self):
        self._client = Neo4jClient

    async def shortest_path_to_vasp(
        self,
        start_address: str,
        chain: str,
        max_hops: int = 6,
    ) -> List[Dict[str, Any]]:
        query = """
        MATCH (start:Wallet {address: $start_address, chain: $chain})
        MATCH (vasp:Entity {entity_type: 'exchange', chain: $chain})
        WHERE vasp.confidence IN ['CONFIRMED', 'HIGH_CONFIDENCE']
        CALL apoc.algo.dijkstra(start, vasp, 'SENT|RECEIVED', 'value') YIELD path, weight
        WHERE length(path) <= $max_hops
        RETURN path, weight, vasp
        ORDER BY weight DESC
        LIMIT 10
        """
        result = await self._client.execute_query(query, {
            "start_address": start_address.lower(),
            "chain": chain,
            "max_hops": max_hops,
        })

        paths = []
        for record in result:
            path = record["path"]
            weight = record["weight"]
            vasp = record["vasp"]

            nodes = []
            edges = []
            for i, node in enumerate(path.nodes):
                if "Wallet" in node.labels:
                    nodes.append({
                        "id": f"Wallet:{node['chain']}:{node['address']}",
                        "type": "wallet",
                        "address": node["address"],
                        "label": node.get("label"),
                        "risk_score": node.get("risk_score", 0),
                    })
                elif "Entity" in node.labels:
                    nodes.append({
                        "id": f"Entity:{node['chain']}:{node['address']}",
                        "type": "entity",
                        "name": node["name"],
                        "entity_type": node["entity_type"],
                        "confidence": node["confidence"],
                    })
                if i > 0:
                    prev = path.nodes[i-1]
                    edges.append({
                        "from": f"Wallet:{prev['chain']}:{prev['address']}",
                        "to": f"Wallet:{node['chain']}:{node['address']}",
                    })

            paths.append({
                "nodes": nodes,
                "edges": edges,
                "total_value": weight,
                "length": len(nodes) - 1,
                "vasp": {
                    "name": vasp["name"],
                    "address": vasp["address"],
                    "confidence": vasp["confidence"],
                },
            })
        return paths

    async def find_mixer_interactions(
        self,
        address: str,
        chain: str,
        max_hops: int = 4,
    ) -> List[Dict[str, Any]]:
        query = """
        MATCH (start:Wallet {address: $address, chain: $chain})
        MATCH (mixer:Entity {entity_type: 'mixer', chain: $chain})
        CALL apoc.algo.dijkstra(start, mixer, 'SENT|RECEIVED', 'value') YIELD path, weight
        WHERE length(path) <= $max_hops
        RETURN path, weight, mixer
        ORDER BY weight DESC
        LIMIT 10
        """
        result = await self._client.execute_query(query, {
            "address": address.lower(),
            "chain": chain,
            "max_hops": max_hops,
        })
        return [dict(r) for r in result]

    async def detect_peel_chains(
        self,
        chain: str,
        min_hops: int = 3,
        min_value_eth: float = 0.1,
        time_window_hours: int = 24,
    ) -> List[Dict[str, Any]]:
        query = """
        MATCH (w:Wallet {chain: $chain})
        WHERE w.tx_count > 10
        MATCH path = (w)-[:SENT*1..$max_hops]->(:Wallet)
        WHERE ALL(r IN relationships(path) WHERE r.value > $min_value)
        AND length(path) >= $min_hops
        WITH w, path, 
             reduce(total = 0, r IN relationships(path) | total + toFloat(r.value)) as total_value,
             [n IN nodes(path) | n.address] as addresses
        WHERE total_value > $min_value * $min_hops
        RETURN w.address as origin, addresses, total_value, length(path) as hops
        ORDER BY total_value DESC
        LIMIT 20
        """
        result = await self._client.execute_query(query, {
            "chain": chain,
            "min_hops": min_hops,
            "max_hops": min_hops + 2,
            "min_value": min_value_eth * 1e18,
        })
        return [dict(r) for r in result]

    async def detect_round_amount_patterns(
        self,
        chain: str,
        min_occurrences: int = 3,
        time_window_hours: int = 24,
    ) -> List[Dict[str, Any]]:
        query = """
        MATCH (t:Transaction {chain: $chain})
        WHERE t.timestamp >= datetime() - duration({hours: $time_window})
        AND toFloat(t.value) % 1 = 0
        AND toFloat(t.value) > 0
        WITH t.from_address as address, t.value, count(*) as occurrences
        WHERE occurrences >= $min_occurrences
        MATCH (w:Wallet {address: address, chain: $chain})
        RETURN address, w.label, w.risk_score, collect(t.value) as values, occurrences
        ORDER BY occurrences DESC
        LIMIT 20
        """
        result = await self._client.execute_query(query, {
            "chain": chain,
            "min_occurrences": min_occurrences,
            "time_window": time_window_hours,
        })
        return [dict(r) for r in result]

    async def detect_rapid_movement(
        self,
        chain: str,
        max_time_between_txs_seconds: int = 300,
        min_hops: int = 3,
    ) -> List[Dict[str, Any]]:
        query = """
        MATCH path = (w1:Wallet {chain: $chain})-[:SENT]->(t1:Transaction)-[:RECEIVED]->(w2:Wallet)-[:SENT]->(t2:Transaction)-[:RECEIVED]->(w3:Wallet)
        WHERE t2.timestamp - t1.timestamp <= duration({seconds: $max_time})
        AND w1 <> w3
        WITH path, w1, w2, w3, t1, t2,
             t2.timestamp - t1.timestamp as time_diff
        WHERE time_diff.seconds <= $max_time
        RETURN w1.address as origin, w2.address as intermediate, w3.address as destination,
               t1.tx_hash as tx1, t2.tx_hash as tx2,
               time_diff.seconds as seconds_between,
               t1.value as value1, t2.value as value2
        ORDER BY seconds_between
        LIMIT 20
        """
        result = await self._client.execute_query(query, {
            "chain": chain,
            "max_time": max_time_between_txs_seconds,
        })
        return [dict(r) for r in result]

    async def get_wallet_centrality(
        self,
        chain: str,
        algorithm: str = "pagerank",
        top_n: int = 50,
    ) -> List[Dict[str, Any]]:
        if algorithm == "pagerank":
            query = """
            CALL gds.pageRank.stream('wallet-graph', {maxIterations: 20, dampingFactor: 0.85})
            YIELD nodeId, score
            WITH gds.util.asNode(nodeId) as node, score
            WHERE node.chain = $chain
            RETURN node.address as address, node.label as label, node.risk_score as risk_score, score
            ORDER BY score DESC
            LIMIT $top_n
            """
        elif algorithm == "betweenness":
            query = """
            CALL gds.betweenness.stream('wallet-graph')
            YIELD nodeId, score
            WITH gds.util.asNode(nodeId) as node, score
            WHERE node.chain = $chain
            RETURN node.address as address, node.label as label, node.risk_score as risk_score, score
            ORDER BY score DESC
            LIMIT $top_n
            """
        else:
            query = """
            MATCH (w:Wallet {chain: $chain})
            RETURN w.address as address, w.label as label, w.risk_score as risk_score, 
                   w.tx_count as score
            ORDER BY w.tx_count DESC
            LIMIT $top_n
            """
        result = await self._client.execute_query(query, {"chain": chain, "top_n": top_n})
        return [dict(r) for r in result]

    async def get_temporal_flow(
        self,
        address: str,
        chain: str,
        start_date: datetime,
        end_date: datetime,
        bucket: str = "day",
    ) -> List[Dict[str, Any]]:
        bucket_format = {
            "hour": "yyyy-MM-dd HH:00",
            "day": "yyyy-MM-dd",
            "week": "yyyy-'W'ww",
        }.get(bucket, "yyyy-MM-dd")

        query = """
        MATCH (w:Wallet {address: $address, chain: $chain})
        MATCH (w)-[:SENT]->(t:Transaction)
        WHERE t.timestamp >= $start_date AND t.timestamp <= $end_date
        RETURN date(t.timestamp) as bucket,
               count(*) as tx_count,
               sum(toFloat(t.value)) as total_value,
               collect(t.tx_hash)[0..5] as sample_txs
        ORDER BY bucket
        """
        result = await self._client.execute_query(query, {
            "address": address.lower(),
            "chain": chain,
            "start_date": start_date,
            "end_date": end_date,
        })
        return [dict(r) for r in result]

    async def get_entity_exposure(
        self,
        entity_address: str,
        chain: str,
        max_hops: int = 2,
    ) -> Dict[str, Any]:
        query = """
        MATCH (e:Entity {address: $entity_address, chain: $chain})
        OPTIONAL MATCH (w:Wallet)-[:BELONGS_TO]->(e)
        OPTIONAL MATCH (w)-[:SENT*1..$max_hops]->(t:Transaction)
        RETURN e,
               count(DISTINCT w) as wallet_count,
               count(DISTINCT t) as tx_count,
               sum(toFloat(t.value)) as total_value,
               collect(DISTINCT w.address)[0..20] as wallet_addresses
        """
        result = await self._client.execute_query(query, {
            "entity_address": entity_address.lower(),
            "chain": chain,
            "max_hops": max_hops,
        })
        if not result:
            return {}
        return dict(result[0])


graph_queries = GraphQueries()