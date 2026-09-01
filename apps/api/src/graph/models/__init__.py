from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ConfidenceLevel(str, Enum):
    CONFIRMED = "CONFIRMED"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    PROBABLE = "PROBABLE"
    UNKNOWN = "UNKNOWN"


class EntityType(str, Enum):
    EXCHANGE = "exchange"
    MIXER = "mixer"
    BRIDGE = "bridge"
    DEFI = "defi"
    SANCTIONED = "sanctioned"
    GAMBLING = "gambling"
    DARKNET = "darknet"
    UNKNOWN = "unknown"


@dataclass
class GraphWallet:
    address: str
    chain: str
    label: str | None = None
    risk_score: float = 0.0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    total_sent: int = 0
    total_received: int = 0
    tx_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    entity_name: str | None = None
    entity_type: EntityType | None = None
    entity_confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN

    @property
    def node_id(self) -> str:
        return f"Wallet:{self.chain}:{self.address.lower()}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "chain": self.chain,
            "label": self.label,
            "risk_score": self.risk_score,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "total_sent": self.total_sent,
            "total_received": self.total_received,
            "tx_count": self.tx_count,
            "metadata": self.metadata,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type.value if self.entity_type else None,
            "entity_confidence": self.entity_confidence.value,
        }


@dataclass
class GraphTransaction:
    tx_hash: str
    chain: str
    block_number: int
    timestamp: datetime
    from_address: str
    to_address: str
    value: str
    value_usd: float | None = None
    token_address: str | None = None
    token_symbol: str | None = None
    method: str | None = None
    gas_used: int | None = None
    gas_price: str | None = None
    is_suspicious: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def node_id(self) -> str:
        return f"Transaction:{self.chain}:{self.tx_hash.lower()}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tx_hash": self.tx_hash,
            "chain": self.chain,
            "block_number": self.block_number,
            "timestamp": self.timestamp.isoformat(),
            "from_address": self.from_address,
            "to_address": self.to_address,
            "value": self.value,
            "value_usd": self.value_usd,
            "token_address": self.token_address,
            "token_symbol": self.token_symbol,
            "method": self.method,
            "gas_used": self.gas_used,
            "gas_price": self.gas_price,
            "is_suspicious": self.is_suspicious,
            "metadata": self.metadata,
        }


@dataclass
class GraphEntity:
    name: str
    entity_type: EntityType
    address: str
    chain: str
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    source: str = "manual"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    first_seen: datetime | None = None
    last_verified: datetime | None = None

    @property
    def node_id(self) -> str:
        return f"Entity:{self.chain}:{self.address.lower()}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "entity_type": self.entity_type.value,
            "address": self.address,
            "chain": self.chain,
            "confidence": self.confidence.value,
            "source": self.source,
            "tags": self.tags,
            "metadata": self.metadata,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
        }


@dataclass
class GraphPath:
    nodes: list[str]
    edges: list[dict[str, Any]]
    total_value: float
    length: int
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    endpoint_entity: GraphEntity | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "total_value": self.total_value,
            "length": self.length,
            "confidence": self.confidence.value,
            "endpoint_entity": self.endpoint_entity.to_dict() if self.endpoint_entity else None,
        }
