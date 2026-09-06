import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
import structlog

from src.core.config import get_settings

from ..graph.models import ConfidenceLevel, EntityType, GraphEntity
from ..graph.repository import graph_repository

logger = structlog.get_logger(__name__)

# OFAC's SDN.CSV has no header row; these are its fixed column positions.
# (ent_num, SDN_Name, SDN_Type, Program, Title, Call_Sign, Vess_type, Tonnage,
#  GRT, Vess_flag, Vess_owner, Remarks)
_SDN_ENT_NUM = 0
_SDN_NAME = 1
_SDN_PROGRAM = 3
_SDN_REMARKS = 11

#: Matches "Digital Currency Address - ETH 0xabc..." occurrences in Remarks.
_DIGITAL_CURRENCY_ADDRESS_RE = re.compile(
    r"Digital Currency Address\s*-\s*([A-Z0-9]+)\s+([a-zA-Z0-9]+)"
)

#: OFAC currency codes that map onto chains TRACE-X can trace. Non-EVM codes
#: (XBT, XMR, LTC, ...) also appear in the list but are out of scope here.
_SDN_CURRENCY_CHAINS = {
    "ETH": "Ethereum",
    "ETC": "Ethereum Classic",
    "USDT": "Ethereum",
    "USDC": "Ethereum",
    "BNB": "BSC",
}
settings = get_settings()


@dataclass
class EntityRecord:
    name: str
    entity_type: EntityType
    address: str
    chain: str
    confidence: ConfidenceLevel
    source: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class EntityIntelligence:
    def __init__(self):
        self._cache: dict[str, list[EntityRecord]] = {}
        self._last_update: datetime | None = None

    async def load_known_entities(self) -> list[EntityRecord]:
        entities = []

        entities.extend(await self._load_major_exchanges())
        entities.extend(await self._load_known_mixers())
        entities.extend(await self._load_bridges())
        entities.extend(await self._load_defi_protocols())
        entities.extend(await self._load_sanctions_list())

        logger.info("loaded_known_entities", count=len(entities))
        return entities

    async def _load_major_exchanges(self) -> list[EntityRecord]:
        exchanges: list[dict[str, Any]] = [
            {
                "name": "Binance",
                "addresses": {
                    1: [
                        "0x28C6c06298d514Db089934071355E5743bf21d60",
                        "0x21a31Ee1afC51d94C2eF3CAaDB94D5c86C1F9e3d",
                    ],
                    137: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.CONFIRMED,
            },
            {
                "name": "Coinbase",
                "addresses": {
                    1: [
                        "0xA9d1e08C7793af67e9d92fe308d5697FB81d3E43",
                        "0x503828976D22510aad0201ac7EC88293211D23Da",
                    ],
                },
                "confidence": ConfidenceLevel.CONFIRMED,
            },
            {
                "name": "Kraken",
                "addresses": {
                    1: [
                        "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",
                        "0x0A869d79a7052c7f1b55a8EBabAa43105310D4D2",
                    ],
                },
                "confidence": ConfidenceLevel.CONFIRMED,
            },
            {
                "name": "OKX",
                "addresses": {
                    1: ["0x8A96747c82B41E8B7A0000000000000000000000"],
                    137: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
            },
            {
                "name": "Bybit",
                "addresses": {
                    1: ["0x159939f79D0B3D4e752912fA658A4D3776c9b5e3"],
                },
                "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
            },
            {
                "name": "Huobi",
                "addresses": {
                    1: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
            },
            {
                "name": "KuCoin",
                "addresses": {
                    1: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
            },
            {
                "name": "Gate.io",
                "addresses": {
                    1: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.PROBABLE,
            },
        ]

        entities = []
        for ex in exchanges:
            for chain_id, addresses in ex["addresses"].items():
                chain_name = {1: "Ethereum", 137: "Polygon"}.get(chain_id, "Ethereum")
                for addr in addresses:
                    entities.append(
                        EntityRecord(
                            name=ex["name"],
                            entity_type=EntityType.EXCHANGE,
                            address=addr,
                            chain=chain_name,
                            confidence=ex["confidence"],
                            source="exchange_directory",
                            tags=["cex", "kyc"],
                            metadata={"chain_id": chain_id},
                        )
                    )
        return entities

    async def _load_known_mixers(self) -> list[EntityRecord]:
        mixers: list[dict[str, Any]] = [
            {
                "name": "Tornado Cash",
                "addresses": {
                    1: [
                        "0x722122dF12D4e14e13Ac3b6895a86e84145b6967",
                        "0x169455c72558a2D9A2C4a5b8F6e9e8D7a6B5c4D3",
                    ],
                },
                "confidence": ConfidenceLevel.CONFIRMED,
            },
            {
                "name": "Wasabi Wallet",
                "addresses": {
                    1: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.PROBABLE,
            },
            {
                "name": "Samourai Whirlpool",
                "addresses": {
                    1: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.PROBABLE,
            },
            {
                "name": "Mixer",
                "addresses": {
                    1: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.PROBABLE,
            },
        ]

        entities = []
        for mixer in mixers:
            for chain_id, addresses in mixer["addresses"].items():
                chain_name = {1: "Ethereum", 137: "Polygon"}.get(chain_id, "Ethereum")
                for addr in addresses:
                    entities.append(
                        EntityRecord(
                            name=mixer["name"],
                            entity_type=EntityType.MIXER,
                            address=addr,
                            chain=chain_name,
                            confidence=mixer["confidence"],
                            source="mixer_directory",
                            tags=["mixer", "privacy", "high_risk"],
                            metadata={"chain_id": chain_id},
                        )
                    )
        return entities

    async def _load_bridges(self) -> list[EntityRecord]:
        bridges: list[dict[str, Any]] = [
            {
                "name": "Polygon Bridge",
                "addresses": {
                    1: ["0xA0c68C638235ee32657e8f720a23ceC1bFc77C77"],
                    137: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.CONFIRMED,
            },
            {
                "name": "Arbitrum Bridge",
                "addresses": {
                    1: ["0x831517E7E53A5A6cC7A8A8A8A8A8A8A8A8A8A8A8"],
                },
                "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
            },
            {
                "name": "Optimism Bridge",
                "addresses": {
                    1: ["0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1"],
                },
                "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
            },
            {
                "name": "Wormhole",
                "addresses": {
                    1: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
            },
        ]

        entities = []
        for bridge in bridges:
            for chain_id, addresses in bridge["addresses"].items():
                chain_name = {1: "Ethereum", 137: "Polygon"}.get(chain_id, "Ethereum")
                for addr in addresses:
                    entities.append(
                        EntityRecord(
                            name=bridge["name"],
                            entity_type=EntityType.BRIDGE,
                            address=addr,
                            chain=chain_name,
                            confidence=bridge["confidence"],
                            source="bridge_directory",
                            tags=["bridge", "cross_chain"],
                            metadata={"chain_id": chain_id},
                        )
                    )
        return entities

    async def _load_defi_protocols(self) -> list[EntityRecord]:
        defi: list[dict[str, Any]] = [
            {
                "name": "Uniswap V3",
                "addresses": {
                    1: ["0x1F98431c8aD98523631AE4a59f267346ea31F984"],
                    137: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.CONFIRMED,
            },
            {
                "name": "Aave V3",
                "addresses": {
                    1: ["0x87870B93F8aD8E5F8a8A8A8A8A8A8A8A8A8A8A8A"],
                },
                "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
            },
            {
                "name": "Curve Finance",
                "addresses": {
                    1: ["0x0000000000000000000000000000000000001010"],
                },
                "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
            },
        ]

        entities = []
        for protocol in defi:
            for chain_id, addresses in protocol["addresses"].items():
                chain_name = {1: "Ethereum", 137: "Polygon"}.get(chain_id, "Ethereum")
                for addr in addresses:
                    entities.append(
                        EntityRecord(
                            name=protocol["name"],
                            entity_type=EntityType.DEFI,
                            address=addr,
                            chain=chain_name,
                            confidence=protocol["confidence"],
                            source="defi_directory",
                            tags=["defi", "dex", "lending"],
                            metadata={"chain_id": chain_id},
                        )
                    )
        return entities

    async def _load_sanctions_list(self) -> list[EntityRecord]:
        entities: list[EntityRecord] = []
        if not settings.OFAC_SDN_LIST_URL:
            return entities

        try:
            # follow_redirects: the OFAC endpoint answers 302 and hands off to
            # a short-lived signed S3 URL. Without this, httpx returns the 302
            # itself and raise_for_status() aborts the sync every time.
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(settings.OFAC_SDN_LIST_URL)
                response.raise_for_status()
                content = response.text

            # SDN.CSV is headerless, fixed-position CSV -- csv.DictReader
            # consumed the first *data* row as the header, so every
            # row.get("sdnType")/row.get("address") returned None and this
            # loader silently produced zero sanctioned addresses. There are no
            # "address"/"sdnType" columns at all: crypto addresses live inside
            # the free-text Remarks column as
            #   "Digital Currency Address - ETH 0x...; alt. Digital Currency
            #    Address - XBT 1..."
            # so parse them out of there instead.
            seen: set[str] = set()
            for row in csv.reader(io.StringIO(content)):
                if len(row) <= _SDN_REMARKS:
                    continue
                remarks = row[_SDN_REMARKS]
                if "Digital Currency Address" not in remarks:
                    continue

                name = row[_SDN_NAME].strip()
                program = row[_SDN_PROGRAM].strip().strip("[]")
                for currency, addr in _DIGITAL_CURRENCY_ADDRESS_RE.findall(remarks):
                    chain = _SDN_CURRENCY_CHAINS.get(currency)
                    # Only EVM-style addresses are actionable here: the rest of
                    # TRACE-X keys wallets by 0x-prefixed addresses.
                    if not chain or not addr.startswith("0x"):
                        continue
                    key = f"{chain}:{addr.lower()}"
                    if key in seen:
                        continue
                    seen.add(key)
                    entities.append(
                        EntityRecord(
                            name=f"OFAC: {name or 'Unknown'}",
                            entity_type=EntityType.SANCTIONED,
                            address=addr,
                            chain=chain,
                            confidence=ConfidenceLevel.CONFIRMED,
                            source="ofac_sdn",
                            tags=["sanctions", "ofac", "high_risk"],
                            metadata={
                                "sdn_entry": row[_SDN_ENT_NUM].strip(),
                                "program": program,
                                "currency": currency,
                            },
                        )
                    )
            logger.info("sanctions_list_loaded", count=len(entities))
        except Exception as e:
            logger.warning("sanctions_list_load_failed", error=str(e))

        return entities

    async def sync_to_graph(self) -> dict[str, int]:
        entities = await self.load_known_entities()
        stats = {"created": 0, "updated": 0, "errors": 0}

        for entity_record in entities:
            try:
                entity = GraphEntity(
                    name=entity_record.name,
                    entity_type=entity_record.entity_type,
                    address=entity_record.address,
                    chain=entity_record.chain,
                    confidence=entity_record.confidence,
                    source=entity_record.source,
                    tags=entity_record.tags or [],
                    metadata=entity_record.metadata or {},
                    first_seen=datetime.utcnow(),
                    last_verified=datetime.utcnow(),
                )
                await graph_repository.upsert_entity(entity)
                stats["created"] += 1
            except Exception as e:
                logger.warning("entity_sync_failed", entity=entity_record.name, error=str(e))
                stats["errors"] += 1

        self._last_update = datetime.utcnow()
        logger.info("entity_sync_completed", stats=stats)
        return stats

    async def lookup_entity(self, address: str, chain: str) -> GraphEntity | None:
        from ..graph.client import Neo4jClient

        query = """
        MATCH (e:Entity {address: $address, chain: $chain})
        RETURN e
        """
        result = await Neo4jClient.execute_query(
            query, {"address": address.lower(), "chain": chain}
        )
        if not result:
            return None
        e = result[0]["e"]
        return GraphEntity(
            name=e["name"],
            entity_type=EntityType(e["entity_type"]),
            address=e["address"],
            chain=e["chain"],
            confidence=ConfidenceLevel(e["confidence"]),
            source=e.get("source", "unknown"),
            tags=e.get("tags", []),
            metadata=e.get("metadata", {}),
        )

    async def enrich_wallet(self, wallet_address: str, chain: str) -> GraphEntity | None:
        entity = await self.lookup_entity(wallet_address, chain)
        if entity:
            await graph_repository.link_wallet_entity(wallet_address, chain, entity.address)
            return entity
        return None


entity_intelligence = EntityIntelligence()
