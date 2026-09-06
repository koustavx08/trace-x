from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

from ..graph.models import ConfidenceLevel, EntityType, GraphEntity, GraphPath
from ..graph.repository import graph_repository

logger = structlog.get_logger(__name__)


class AttributionType(str, Enum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    CLUSTER = "cluster"
    HEURISTIC = "heuristic"


@dataclass
class AttributionEvidence:
    source: str
    evidence_type: str
    description: str
    confidence: ConfidenceLevel
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class VASPAttribution:
    entity_name: str
    entity_type: EntityType
    address: str
    chain: str
    attribution_type: AttributionType
    confidence: ConfidenceLevel
    confidence_score: float
    distance_hops: int
    total_value_eth: float
    evidence: list[AttributionEvidence]
    path: GraphPath | None = None
    attributed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_name": self.entity_name,
            "entity_type": self.entity_type.value,
            "address": self.address,
            "chain": self.chain,
            "attribution_type": self.attribution_type.value,
            "confidence": self.confidence.value,
            "confidence_score": round(self.confidence_score, 2),
            "distance_hops": self.distance_hops,
            "total_value_eth": round(self.total_value_eth, 6),
            "evidence": [
                {
                    "source": e.source,
                    "evidence_type": e.evidence_type,
                    "description": e.description,
                    "confidence": e.confidence.value,
                    "data": e.data,
                }
                for e in self.evidence
            ],
            "path": self.path.to_dict() if self.path else None,
            "attributed_at": self.attributed_at.isoformat(),
        }


CONFIDENCE_SCORES = {
    ConfidenceLevel.CONFIRMED: 1.0,
    ConfidenceLevel.HIGH_CONFIDENCE: 0.85,
    ConfidenceLevel.PROBABLE: 0.65,
    ConfidenceLevel.UNKNOWN: 0.3,
}

ATTRIBUTION_WEIGHTS = {
    AttributionType.DIRECT: 1.0,
    AttributionType.INDIRECT: 0.8,
    AttributionType.CLUSTER: 0.6,
    AttributionType.HEURISTIC: 0.4,
}


class AttributionEngine:
    def __init__(self):
        self.logger = logger.bind(component="attribution_engine")

    async def attribute_wallet(
        self,
        wallet_address: str,
        chain: str,
        max_hops: int = 6,
    ) -> list[VASPAttribution]:
        paths = await graph_repository.find_paths_to_entities(
            start_address=wallet_address,
            chain=chain,
            entity_types=[EntityType.EXCHANGE, EntityType.BRIDGE, EntityType.DEFI],
            max_depth=max_hops,
            min_confidence=ConfidenceLevel.PROBABLE,
            limit=20,
        )

        attributions = []
        for path in paths:
            if path.endpoint_entity:
                attribution = await self._create_attribution(path, wallet_address, chain)
                if attribution:
                    attributions.append(attribution)

        attributions.sort(key=lambda a: (-a.confidence_score, a.distance_hops))
        return attributions[:10]

    async def _create_attribution(
        self,
        path: GraphPath,
        wallet_address: str,
        chain: str,
    ) -> VASPAttribution | None:
        if not path.endpoint_entity:
            return None

        entity = path.endpoint_entity

        evidence = []

        evidence.append(
            AttributionEvidence(
                source="graph_traversal",
                evidence_type="on_chain_path",
                description=f"Fund flow path: {path.length} hops, {path.total_value:.6f} ETH",
                confidence=path.confidence,
                data={
                    "path_length": path.length,
                    "total_value_eth": path.total_value,
                    "nodes": path.nodes,
                },
            )
        )

        evidence.append(
            AttributionEvidence(
                source="entity_registry",
                evidence_type="off_chain_intelligence",
                description=f"Known {entity.entity_type.value}: {entity.name} ({entity.confidence.value})",
                confidence=entity.confidence,
                data={
                    "entity_name": entity.name,
                    "entity_type": entity.entity_type.value,
                    "entity_address": entity.address,
                    "source": entity.source,
                    "tags": entity.tags,
                },
            )
        )

        if entity.confidence == ConfidenceLevel.CONFIRMED:
            evidence.append(
                AttributionEvidence(
                    source="manual_verification",
                    evidence_type="verified_attribution",
                    description="Entity verified through multiple independent sources",
                    confidence=ConfidenceLevel.CONFIRMED,
                    data={"verification_method": "multi_source"},
                )
            )

        attribution_type = self._determine_attribution_type(path, entity)
        confidence = self._calculate_confidence(path, entity, attribution_type)
        confidence_score = self._calculate_confidence_score(
            confidence, path, entity, attribution_type
        )

        return VASPAttribution(
            entity_name=entity.name,
            entity_type=entity.entity_type,
            address=entity.address,
            chain=chain,
            attribution_type=attribution_type,
            confidence=confidence,
            confidence_score=confidence_score,
            distance_hops=path.length,
            total_value_eth=path.total_value,
            evidence=evidence,
            path=path,
        )

    def _determine_attribution_type(
        self,
        path: GraphPath,
        entity: GraphEntity,
    ) -> AttributionType:
        if path.length == 1:
            return AttributionType.DIRECT

        if entity.confidence == ConfidenceLevel.CONFIRMED and path.length <= 2:
            return AttributionType.DIRECT

        if entity.entity_type in [EntityType.EXCHANGE, EntityType.BRIDGE]:
            return AttributionType.INDIRECT

        if entity.entity_type == EntityType.DEFI:
            return AttributionType.HEURISTIC

        return AttributionType.INDIRECT

    def _calculate_confidence(
        self,
        path: GraphPath,
        entity: GraphEntity,
        attribution_type: AttributionType,
    ) -> ConfidenceLevel:
        base_confidence = entity.confidence

        if base_confidence == ConfidenceLevel.CONFIRMED:
            if path.length <= 2 and attribution_type == AttributionType.DIRECT:
                return ConfidenceLevel.CONFIRMED
            elif path.length <= 4:
                return ConfidenceLevel.HIGH_CONFIDENCE
            else:
                return ConfidenceLevel.PROBABLE

        elif base_confidence == ConfidenceLevel.HIGH_CONFIDENCE:
            if path.length <= 3:
                return ConfidenceLevel.HIGH_CONFIDENCE
            else:
                return ConfidenceLevel.PROBABLE

        elif base_confidence == ConfidenceLevel.PROBABLE:
            if path.length <= 2:
                return ConfidenceLevel.PROBABLE
            else:
                return ConfidenceLevel.UNKNOWN

        return ConfidenceLevel.UNKNOWN

    def _calculate_confidence_score(
        self,
        confidence: ConfidenceLevel,
        path: GraphPath,
        entity: GraphEntity,
        attribution_type: AttributionType,
    ) -> float:
        base_score = CONFIDENCE_SCORES[confidence]
        path_penalty = max(0, 1 - (path.length - 1) * 0.1)
        type_weight = ATTRIBUTION_WEIGHTS[attribution_type]
        value_factor = min(1.0, path.total_value / 10.0) if path.total_value > 0 else 0.5

        score = base_score * path_penalty * type_weight * (0.7 + 0.3 * value_factor)
        return min(max(score, 0.0), 1.0)

    async def get_attribution_summary(
        self,
        wallet_address: str,
        chain: str,
    ) -> dict[str, Any]:
        attributions = await self.attribute_wallet(wallet_address, chain)

        if not attributions:
            # Must carry the same keys as the populated branch below: this dict
            # is fed straight into `AttributionResponse(**result)`, which
            # requires `all_attributions` and `summary`. Omitting them made the
            # "nothing attributed" case -- the normal outcome whenever no
            # blockchain provider is configured -- fail with a 500 instead of
            # honestly reporting that there was nothing to attribute.
            return {
                "attributed": False,
                "nearest_vasp": None,
                "confidence": ConfidenceLevel.UNKNOWN.value,
                "total_attributions": 0,
                "all_attributions": [],
                "summary": {
                    "exchanges_found": 0,
                    "mixers_found": 0,
                    "bridges_found": 0,
                    "highest_confidence": 0.0,
                    "average_hops": 0.0,
                },
            }

        primary = attributions[0]
        exchanges = [a for a in attributions if a.entity_type == EntityType.EXCHANGE]
        mixers = [a for a in attributions if a.entity_type == EntityType.MIXER]
        bridges = [a for a in attributions if a.entity_type == EntityType.BRIDGE]

        return {
            "attributed": True,
            "nearest_vasp": {
                "entity_name": primary.entity_name,
                "entity_type": primary.entity_type.value,
                "address": primary.address,
                "confidence": primary.confidence.value,
                "confidence_score": primary.confidence_score,
                "distance_hops": primary.distance_hops,
                "total_value_eth": primary.total_value_eth,
            },
            "all_attributions": [a.to_dict() for a in attributions],
            "summary": {
                "exchanges_found": len(exchanges),
                "mixers_found": len(mixers),
                "bridges_found": len(bridges),
                "highest_confidence": max(a.confidence_score for a in attributions),
                "average_hops": sum(a.distance_hops for a in attributions) / len(attributions),
            },
        }


attribution_engine = AttributionEngine()
