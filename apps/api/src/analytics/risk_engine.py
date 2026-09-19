from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from ..graph.models import ConfidenceLevel, EntityType, GraphTransaction, GraphWallet

logger = structlog.get_logger(__name__)


def _age_in_days(moment: datetime) -> int:
    """Whole days between `moment` and now, tolerating naive or aware inputs.

    Timestamps read back from Neo4j are timezone-aware, while ones built in
    Python here were naive (`datetime.utcnow()`), and subtracting one from the
    other raises "can't subtract offset-naive and offset-aware datetimes".
    Naive values are treated as UTC, which is what every producer in this
    codebase writes.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return (datetime.now(UTC) - moment).days


class RiskFactorType(str, Enum):
    MIXER_INTERACTION = "mixer_interaction"
    PEEL_CHAIN = "peel_chain"
    ROUND_AMOUNTS = "round_amounts"
    RAPID_MOVEMENT = "rapid_movement"
    HIGH_RISK_ENTITY = "high_risk_entity"
    SANCTIONS_HIT = "sanctions_hit"
    LARGE_VALUE_TRANSFER = "large_value_transfer"
    CROSS_CHAIN_BRIDGE = "cross_chain_bridge"
    NEW_WALLET = "new_wallet"
    LOW_LIQUIDITY_TOKEN = "low_liquidity_token"
    CONTRACT_INTERACTION = "contract_interaction"
    DUSTING_ATTACK = "dusting_attack"


class RiskSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class RiskFactor:
    factor_type: RiskFactorType
    severity: RiskSeverity
    score: float
    weight: float
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class RiskAssessment:
    overall_score: float
    risk_level: RiskSeverity
    factors: list[RiskFactor]
    summary: str
    methodology: str
    assessed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 2),
            "risk_level": self.risk_level.value,
            "factors": [
                {
                    "type": f.factor_type.value,
                    "severity": f.severity.value,
                    "score": f.score,
                    "weight": f.weight,
                    "weighted_score": round(f.weighted_score, 2),
                    "description": f.description,
                    "evidence": f.evidence,
                    "confidence": f.confidence.value,
                }
                for f in self.factors
            ],
            "total_weighted_score": round(sum(f.weighted_score for f in self.factors), 2),
            "active_factors_count": len([f for f in self.factors if f.score > 0]),
            "clean_factors_count": len([f for f in self.factors if f.score == 0]),
            "summary": self.summary,
            "methodology": self.methodology,
            "assessed_at": self.assessed_at.isoformat(),
        }


RISK_WEIGHTS = {
    RiskFactorType.MIXER_INTERACTION: 0.25,
    RiskFactorType.PEEL_CHAIN: 0.20,
    RiskFactorType.SANCTIONS_HIT: 0.30,
    RiskFactorType.HIGH_RISK_ENTITY: 0.15,
    RiskFactorType.RAPID_MOVEMENT: 0.10,
    RiskFactorType.ROUND_AMOUNTS: 0.08,
    RiskFactorType.LARGE_VALUE_TRANSFER: 0.07,
    RiskFactorType.CROSS_CHAIN_BRIDGE: 0.05,
    RiskFactorType.CONTRACT_INTERACTION: 0.05,
    RiskFactorType.NEW_WALLET: 0.03,
    RiskFactorType.LOW_LIQUIDITY_TOKEN: 0.02,
    RiskFactorType.DUSTING_ATTACK: 0.02,
}

SEVERITY_THRESHOLDS = {
    RiskSeverity.CRITICAL: 80,
    RiskSeverity.HIGH: 60,
    RiskSeverity.MEDIUM: 40,
    RiskSeverity.LOW: 5,
    RiskSeverity.INFO: 0,
}

CLEAN_FACTOR_DESCRIPTIONS: dict[RiskFactorType, str] = {
    RiskFactorType.SANCTIONS_HIT: "Evaluated: No matches across OFAC SDN, MHA, EU, or UN international sanctions lists.",
    RiskFactorType.MIXER_INTERACTION: "Evaluated: No direct or multi-hop deposit/withdrawal interactions with privacy mixers.",
    RiskFactorType.HIGH_RISK_ENTITY: "Evaluated: Counterparty addresses verified clean of known illicit or darknet tags.",
    RiskFactorType.PEEL_CHAIN: "Evaluated: No asymmetric peel chains or automated split fan-out patterns detected.",
    RiskFactorType.RAPID_MOVEMENT: "Evaluated: Transaction velocity normal; no sub-5 minute automated hopping detected.",
    RiskFactorType.ROUND_AMOUNTS: "Evaluated: Natural value dispersion; no systemic integer smurfing patterns.",
    RiskFactorType.LARGE_VALUE_TRANSFER: "Evaluated: Transaction amounts remain within typical historical volume thresholds.",
    RiskFactorType.CROSS_CHAIN_BRIDGE: "Evaluated: No cross-chain bridge lock/mint hops or chain-hopping maneuvers.",
    RiskFactorType.CONTRACT_INTERACTION: "Evaluated: Standard contract interactions; no anomalous proxy or router manipulations.",
    RiskFactorType.NEW_WALLET: "Evaluated: Matured wallet address (> 30 days active history, established activity).",
    RiskFactorType.LOW_LIQUIDITY_TOKEN: "Evaluated: Asset composition consists of established high-liquidity tokens.",
    RiskFactorType.DUSTING_ATTACK: "Evaluated: No unsolicited micro-dust injections or tracking transaction spam.",
}

ALL_12_FACTOR_ORDER: list[RiskFactorType] = [
    RiskFactorType.SANCTIONS_HIT,
    RiskFactorType.MIXER_INTERACTION,
    RiskFactorType.HIGH_RISK_ENTITY,
    RiskFactorType.PEEL_CHAIN,
    RiskFactorType.RAPID_MOVEMENT,
    RiskFactorType.ROUND_AMOUNTS,
    RiskFactorType.LARGE_VALUE_TRANSFER,
    RiskFactorType.CROSS_CHAIN_BRIDGE,
    RiskFactorType.CONTRACT_INTERACTION,
    RiskFactorType.NEW_WALLET,
    RiskFactorType.LOW_LIQUIDITY_TOKEN,
    RiskFactorType.DUSTING_ATTACK,
]


class RiskScoringEngine:
    def __init__(self):
        self.logger = logger.bind(component="risk_engine")

    async def assess_wallet(
        self,
        wallet: GraphWallet,
        transactions: list[GraphTransaction],
        entity_data: dict[str, Any] | None = None,
        graph_context: dict[str, Any] | None = None,
    ) -> RiskAssessment:
        elevated_factors: list[RiskFactor] = []

        elevated_factors.extend(await self._check_sanctions(wallet, entity_data))
        elevated_factors.extend(
            await self._check_mixer_interaction(wallet, transactions, graph_context, entity_data)
        )
        elevated_factors.extend(await self._check_high_risk_entities(wallet, entity_data))
        elevated_factors.extend(await self._check_peel_chain(wallet, transactions, graph_context))
        elevated_factors.extend(await self._check_rapid_movement(transactions))
        elevated_factors.extend(await self._check_round_amounts(transactions))
        elevated_factors.extend(
            await self._check_large_transfers(transactions, wallet, entity_data)
        )
        elevated_factors.extend(await self._check_cross_chain_bridges(transactions))
        elevated_factors.extend(await self._check_contract_interactions(transactions))
        elevated_factors.extend(await self._check_new_wallet(wallet))
        elevated_factors.extend(await self._check_low_liquidity_tokens(transactions))
        elevated_factors.extend(await self._check_dusting_attacks(transactions))

        # Map highest severity/score factor for each elevated factor type
        elevated_map: dict[RiskFactorType, RiskFactor] = {}
        for factor in elevated_factors:
            if (
                factor.factor_type not in elevated_map
                or factor.score > elevated_map[factor.factor_type].score
            ):
                elevated_map[factor.factor_type] = factor

        # Assemble full 12 factors (elevated first in priority order, then clean)
        factors: list[RiskFactor] = []
        for ft in ALL_12_FACTOR_ORDER:
            if ft in elevated_map:
                factors.append(elevated_map[ft])

        for ft in ALL_12_FACTOR_ORDER:
            if ft not in elevated_map:
                factors.append(
                    RiskFactor(
                        factor_type=ft,
                        severity=RiskSeverity.LOW,
                        score=0.0,
                        weight=RISK_WEIGHTS[ft],
                        description=CLEAN_FACTOR_DESCRIPTIONS.get(
                            ft, f"Evaluated: No elevated threat signals detected for {ft.value}."
                        ),
                        evidence={"status": "clean", "detected": False},
                        confidence=ConfidenceLevel.CONFIRMED,
                    )
                )

        overall_score = self._calculate_overall_score(factors)
        risk_level = self._score_to_severity(overall_score)
        summary = self._generate_summary(factors, overall_score, risk_level)

        return RiskAssessment(
            overall_score=overall_score,
            risk_level=risk_level,
            factors=factors,
            summary=summary,
            methodology=self._get_methodology(),
        )

    async def _check_mixer_interaction(
        self,
        wallet: GraphWallet,
        transactions: list[GraphTransaction],
        graph_context: dict[str, Any] | None,
        entity_data: dict[str, Any] | None = None,
    ) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        if not graph_context:
            return factors

        mixer_interactions = graph_context.get("mixer_interactions", [])
        if not mixer_interactions:
            return factors

        # Detect if this wallet is recognized infrastructure (DEX router, exchange, bridge)
        if wallet and wallet.entity_type is not None:
            wallet_ent_val = getattr(wallet.entity_type, "value", wallet.entity_type)
        else:
            wallet_ent_val = None
        raw_entity_type = (
            entity_data.get("entity_type") if entity_data else None
        ) or wallet_ent_val
        if raw_entity_type is not None:
            raw_entity_type = getattr(raw_entity_type, "value", raw_entity_type)
        raw_type_str = str(raw_entity_type).lower() if raw_entity_type else ""

        label_str = (wallet.label or "").lower()
        name_str = (wallet.entity_name or ((entity_data or {}).get("entity_name") or "")).lower()

        is_infra = raw_type_str in ("defi", "exchange", "bridge", "merchant") or any(
            t in label_str or t in name_str
            for t in [
                "uniswap",
                "sushiswap",
                "curve",
                "aave",
                "binance",
                "kraken",
                "coinbase",
                "router",
                "exchange",
                "dex",
            ]
        )

        seen_mixers: set[tuple] = set()
        for interaction in mixer_interactions:
            mixer_name = interaction.get("mixer", {}).get("name", "Unknown Mixer")
            mixer_addr = interaction.get("mixer", {}).get("address", "")

            # Read hops from Cypher output, or calculate from path nodes, or fallback to length
            hops = interaction.get("hops")
            if hops is None:
                path = interaction.get("path")
                if path and hasattr(path, "nodes"):
                    wallet_nodes = [
                        n for n in path.nodes if hasattr(n, "labels") and "Wallet" in n.labels
                    ]
                    hops = max(1, len(wallet_nodes) - 1)
                else:
                    hops = interaction.get("length", 1)

            value = interaction.get("weight", 0)
            mixer_key = (mixer_name, hops, round(value, 4))
            if mixer_key in seen_mixers:
                continue
            seen_mixers.add(mixer_key)

            # Self-is-mixer check
            if hops == 0 or (wallet.address.lower() == mixer_addr.lower()):
                score = 99.0
                severity = RiskSeverity.CRITICAL
                desc = f"Identified privacy mixer service ({mixer_name})"
                conf = ConfidenceLevel.CONFIRMED
            elif is_infra:
                # Infrastructure entities act as execution venues or passive counterparties
                if hops <= 1:
                    score = 15.0
                    severity = RiskSeverity.LOW
                    desc = f"Direct mixer interaction with infrastructure ({mixer_name}): passive execution venue ({hops} hop, {value:.4f} ETH)"
                    conf = ConfidenceLevel.CONFIRMED
                elif hops == 2:
                    score = 8.0
                    severity = RiskSeverity.LOW
                    desc = f"Indirect mixer inflow ({mixer_name}, {hops} hops): bonafide merchant/router counterparty ({value:.4f} ETH)"
                    conf = ConfidenceLevel.CONFIRMED
                else:
                    # Negligible indirect exposure for public infrastructure
                    continue
            else:
                # Standard suspect or mule wallet: apply distance attenuation
                if hops <= 1:
                    score = 95.0
                    severity = RiskSeverity.CRITICAL
                    desc = f"Direct funds flow with privacy mixer {mixer_name} ({hops} hop, {value:.4f} ETH)"
                    conf = ConfidenceLevel.HIGH_CONFIDENCE
                elif hops == 2:
                    score = 50.0
                    severity = RiskSeverity.MEDIUM
                    desc = f"Funds traced through {mixer_name} ({hops} hops, {value:.4f} ETH)"
                    conf = ConfidenceLevel.HIGH_CONFIDENCE
                elif hops == 3:
                    score = 25.0
                    severity = RiskSeverity.LOW
                    desc = f"Diluted multi-hop trace to {mixer_name} ({hops} hops, {value:.4f} ETH)"
                    conf = ConfidenceLevel.PROBABLE
                else:
                    score = 10.0
                    severity = RiskSeverity.INFO
                    desc = f"Distant trace to {mixer_name} ({hops} hops, {value:.4f} ETH)"
                    conf = ConfidenceLevel.PROBABLE

            factors.append(
                RiskFactor(
                    factor_type=RiskFactorType.MIXER_INTERACTION,
                    severity=severity,
                    score=score,
                    weight=RISK_WEIGHTS[RiskFactorType.MIXER_INTERACTION],
                    description=desc,
                    evidence={
                        "mixer_name": mixer_name,
                        "hops_from_wallet": hops,
                        "value_eth": value,
                        "is_infrastructure": is_infra,
                        "path": interaction.get("nodes", []),
                    },
                    confidence=conf,
                )
            )

        return factors

    async def _check_peel_chain(
        self,
        wallet: GraphWallet,
        transactions: list[GraphTransaction],
        graph_context: dict[str, Any] | None,
    ) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        if not graph_context:
            return factors

        peel_chains = graph_context.get("peel_chains", [])
        if not peel_chains:
            return factors

        seen_chains: set[tuple] = set()
        for chain in peel_chains:
            if chain.get("origin") == wallet.address.lower():
                hops = chain.get("hops", 0)
                total_value = chain.get("total_value", 0)
                addresses = chain.get("addresses", [])

                # Verify distinct addresses - cycles/loops are not peel chains!
                if len(addresses) != len(set(addresses)) or len(addresses) < 3:
                    continue

                chain_key = (tuple(addresses), hops)
                if chain_key in seen_chains:
                    continue
                seen_chains.add(chain_key)

                factors.append(
                    RiskFactor(
                        factor_type=RiskFactorType.PEEL_CHAIN,
                        severity=RiskSeverity.HIGH,
                        score=85,
                        weight=RISK_WEIGHTS[RiskFactorType.PEEL_CHAIN],
                        description=f"Peel chain detected: {hops} hops, {len(addresses)} addresses, {total_value:.4f} ETH total",
                        evidence={
                            "hops": hops,
                            "address_count": len(addresses),
                            "total_value_eth": total_value,
                            "addresses": addresses[:10],
                        },
                        confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                    )
                )

        return factors

    async def _check_round_amounts(self, transactions: list[GraphTransaction]) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        round_txs = []
        for tx in transactions:
            try:
                value = float(tx.value) / 1e18 if tx.value.isdigit() else 0
                if value > 0 and value == int(value) and value >= 1:
                    round_txs.append((tx, value))
            except (ValueError, AttributeError):
                continue

        if len(round_txs) >= 3:
            values = [v for _, v in round_txs]
            unique_values = len(set(values))

            factors.append(
                RiskFactor(
                    factor_type=RiskFactorType.ROUND_AMOUNTS,
                    severity=RiskSeverity.MEDIUM if len(round_txs) >= 5 else RiskSeverity.LOW,
                    score=60 if len(round_txs) >= 5 else 35,
                    weight=RISK_WEIGHTS[RiskFactorType.ROUND_AMOUNTS],
                    description=f"{len(round_txs)} transactions with round ETH amounts ({unique_values} unique values)",
                    evidence={
                        "round_transaction_count": len(round_txs),
                        "unique_amounts": unique_values,
                        "amounts": sorted(set(values))[:10],
                        "sample_tx_hashes": [tx.tx_hash for tx, _ in round_txs[:5]],
                    },
                    confidence=ConfidenceLevel.PROBABLE,
                )
            )

        return factors

    async def _check_rapid_movement(self, transactions: list[GraphTransaction]) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        sorted_txs = sorted(transactions, key=lambda t: t.timestamp)
        rapid_sequences: list[dict[str, Any]] = []

        for i in range(1, len(sorted_txs)):
            time_diff = (sorted_txs[i].timestamp - sorted_txs[i - 1].timestamp).total_seconds()
            if time_diff < 300:
                rapid_sequences.append(
                    {
                        "tx1": sorted_txs[i - 1].tx_hash,
                        "tx2": sorted_txs[i].tx_hash,
                        "seconds": time_diff,
                    }
                )

        if len(rapid_sequences) >= 3:
            factors.append(
                RiskFactor(
                    factor_type=RiskFactorType.RAPID_MOVEMENT,
                    severity=RiskSeverity.HIGH
                    if len(rapid_sequences) >= 5
                    else RiskSeverity.MEDIUM,
                    score=75 if len(rapid_sequences) >= 5 else 50,
                    weight=RISK_WEIGHTS[RiskFactorType.RAPID_MOVEMENT],
                    description=f"{len(rapid_sequences)} rapid transaction sequences (< 5 min between txs)",
                    evidence={
                        "sequence_count": len(rapid_sequences),
                        "min_interval_seconds": min(s["seconds"] for s in rapid_sequences),
                        "sequences": rapid_sequences[:5],
                    },
                    confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                )
            )

        return factors

    async def _check_high_risk_entities(
        self,
        wallet: GraphWallet,
        entity_data: dict[str, Any] | None,
    ) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        if not entity_data:
            return factors

        # entity_type/confidence may arrive as plain strings (e.g. read back
        # from DB columns) rather than enum members -- normalize both so
        # `.value` below always works.
        raw_entity_type = entity_data.get("entity_type")
        try:
            entity_type = EntityType(raw_entity_type) if raw_entity_type else None
        except ValueError:
            entity_type = None
        entity_name = entity_data.get("entity_name", "Unknown")
        raw_confidence = entity_data.get("confidence", ConfidenceLevel.UNKNOWN)
        try:
            confidence = (
                ConfidenceLevel(raw_confidence) if raw_confidence else ConfidenceLevel.UNKNOWN
            )
        except ValueError:
            confidence = ConfidenceLevel.UNKNOWN

        high_risk_types = {
            EntityType.MIXER: (RiskSeverity.CRITICAL, 95, "Known mixer/tumbler service"),
            EntityType.SANCTIONED: (RiskSeverity.CRITICAL, 100, "Sanctioned entity (OFAC/UN/EU)"),
            EntityType.DARKNET: (RiskSeverity.CRITICAL, 90, "Darknet market association"),
            EntityType.GAMBLING: (RiskSeverity.HIGH, 70, "Gambling platform"),
        }

        if entity_type in high_risk_types:
            severity, score, desc = high_risk_types[entity_type]
            factors.append(
                RiskFactor(
                    factor_type=RiskFactorType.HIGH_RISK_ENTITY,
                    severity=severity,
                    score=score,
                    weight=RISK_WEIGHTS[RiskFactorType.HIGH_RISK_ENTITY],
                    description=f"Direct interaction with {desc}: {entity_name}",
                    evidence={
                        "entity_name": entity_name,
                        "entity_type": entity_type.value if entity_type else "unknown",
                        "confidence": confidence.value
                        if confidence
                        else ConfidenceLevel.UNKNOWN.value,
                    },
                    confidence=confidence,
                )
            )

        return factors

    async def _check_sanctions(
        self,
        wallet: GraphWallet,
        entity_data: dict[str, Any] | None,
    ) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        if not entity_data:
            return factors

        if entity_data.get("entity_type") == EntityType.SANCTIONED:
            sdn_entry = entity_data.get("metadata", {}).get("sdn_entry", "Unknown")
            program = entity_data.get("metadata", {}).get("program", "Unknown")

            factors.append(
                RiskFactor(
                    factor_type=RiskFactorType.SANCTIONS_HIT,
                    severity=RiskSeverity.CRITICAL,
                    score=100,
                    weight=RISK_WEIGHTS[RiskFactorType.SANCTIONS_HIT],
                    description=f"OFAC SDN Match: {entity_data.get('entity_name', 'Unknown')} (Program: {program})",
                    evidence={
                        "entity_name": entity_data.get("entity_name"),
                        "sdn_entry": sdn_entry,
                        "sanctions_program": program,
                        "source": "ofac_sdn",
                    },
                    confidence=ConfidenceLevel.CONFIRMED,
                )
            )

        return factors

    async def _check_large_transfers(
        self,
        transactions: list[GraphTransaction],
        wallet: GraphWallet | None = None,
        entity_data: dict[str, Any] | None = None,
    ) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        # Known infrastructure (DEX routers, CEXs) routinely process large volume as standard liquidity
        if wallet:
            if wallet.entity_type is not None:
                wallet_ent_val = getattr(wallet.entity_type, "value", wallet.entity_type)
            else:
                wallet_ent_val = None
            raw_entity_type = (
                entity_data.get("entity_type") if entity_data else None
            ) or wallet_ent_val
            if raw_entity_type is not None:
                raw_entity_type = getattr(raw_entity_type, "value", raw_entity_type)
            raw_type_str = str(raw_entity_type).lower() if raw_entity_type else ""
            label_str = (wallet.label or "").lower()
            name_str = (
                wallet.entity_name or ((entity_data or {}).get("entity_name") or "")
            ).lower()

            if raw_type_str in ("defi", "exchange", "bridge", "merchant") or any(
                t in label_str or t in name_str
                for t in [
                    "uniswap",
                    "sushiswap",
                    "curve",
                    "aave",
                    "binance",
                    "kraken",
                    "coinbase",
                    "router",
                    "exchange",
                    "dex",
                ]
            ):
                return factors

        large_txs = []
        for tx in transactions:
            try:
                value = float(tx.value) / 1e18 if tx.value.isdigit() else 0
                if value >= 100:
                    large_txs.append((tx, value))
            except (ValueError, AttributeError):
                continue

        if large_txs:
            max_value = max(v for _, v in large_txs)
            total_value = sum(v for _, v in large_txs)

            factors.append(
                RiskFactor(
                    factor_type=RiskFactorType.LARGE_VALUE_TRANSFER,
                    severity=RiskSeverity.HIGH if max_value >= 1000 else RiskSeverity.MEDIUM,
                    score=70 if max_value >= 1000 else 50,
                    weight=RISK_WEIGHTS[RiskFactorType.LARGE_VALUE_TRANSFER],
                    description=f"{len(large_txs)} large transfers (>100 ETH), max: {max_value:.2f} ETH",
                    evidence={
                        "large_transfer_count": len(large_txs),
                        "max_value_eth": max_value,
                        "total_value_eth": total_value,
                        "tx_hashes": [tx.tx_hash for tx, _ in large_txs[:5]],
                    },
                    confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                )
            )

        return factors

    async def _check_cross_chain_bridges(
        self, transactions: list[GraphTransaction]
    ) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        bridge_txs = [
            tx
            for tx in transactions
            if tx.token_symbol
            and tx.token_symbol.upper() in ["USDC", "USDT", "WETH", "MATIC"]
            and tx.method
            and "bridge" in tx.method.lower()
        ]

        if bridge_txs:
            factors.append(
                RiskFactor(
                    factor_type=RiskFactorType.CROSS_CHAIN_BRIDGE,
                    severity=RiskSeverity.MEDIUM,
                    score=45,
                    weight=RISK_WEIGHTS[RiskFactorType.CROSS_CHAIN_BRIDGE],
                    description=f"{len(bridge_txs)} cross-chain bridge transactions detected",
                    evidence={
                        "bridge_tx_count": len(bridge_txs),
                        "tokens": list({tx.token_symbol for tx in bridge_txs if tx.token_symbol}),
                        "tx_hashes": [tx.tx_hash for tx in bridge_txs[:5]],
                    },
                    confidence=ConfidenceLevel.PROBABLE,
                )
            )

        return factors

    async def _check_new_wallet(self, wallet: GraphWallet) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        if wallet.first_seen and wallet.tx_count < 5:
            days_old = _age_in_days(wallet.first_seen)
            if days_old < 30:
                factors.append(
                    RiskFactor(
                        factor_type=RiskFactorType.NEW_WALLET,
                        severity=RiskSeverity.LOW,
                        score=25,
                        weight=RISK_WEIGHTS[RiskFactorType.NEW_WALLET],
                        description=f"New wallet ({days_old} days old, {wallet.tx_count} transactions)",
                        evidence={
                            "wallet_age_days": days_old,
                            "transaction_count": wallet.tx_count,
                        },
                        confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                    )
                )

        return factors

    async def _check_contract_interactions(
        self, transactions: list[GraphTransaction]
    ) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        contract_txs = [tx for tx in transactions if tx.method and tx.method != "transfer"]
        if len(contract_txs) > 10:
            unique_methods = len({tx.method for tx in contract_txs if tx.method})

            factors.append(
                RiskFactor(
                    factor_type=RiskFactorType.CONTRACT_INTERACTION,
                    severity=RiskSeverity.LOW,
                    score=30,
                    weight=RISK_WEIGHTS[RiskFactorType.CONTRACT_INTERACTION],
                    description=f"High contract interaction: {len(contract_txs)} contract calls, {unique_methods} unique methods",
                    evidence={
                        "contract_tx_count": len(contract_txs),
                        "unique_methods": unique_methods,
                        "methods": list({tx.method for tx in contract_txs if tx.method})[:10],
                    },
                    confidence=ConfidenceLevel.PROBABLE,
                )
            )

        return factors

    async def _check_low_liquidity_tokens(
        self, transactions: list[GraphTransaction]
    ) -> list[RiskFactor]:
        factors: list[RiskFactor] = []
        suspicious_tokens = []
        for tx in transactions:
            sym = (tx.token_symbol or "").upper()
            if tx.token_address and (not sym or len(sym) > 10 or "SCAM" in sym or "FAKE" in sym):
                suspicious_tokens.append(tx)

        if suspicious_tokens:
            factors.append(
                RiskFactor(
                    factor_type=RiskFactorType.LOW_LIQUIDITY_TOKEN,
                    severity=RiskSeverity.MEDIUM,
                    score=55,
                    weight=RISK_WEIGHTS[RiskFactorType.LOW_LIQUIDITY_TOKEN],
                    description=f"{len(suspicious_tokens)} transfers involving unverified or low-liquidity tokens",
                    evidence={
                        "token_count": len(suspicious_tokens),
                        "sample_hashes": [tx.tx_hash for tx in suspicious_tokens[:5]],
                    },
                    confidence=ConfidenceLevel.PROBABLE,
                )
            )
        return factors

    async def _check_dusting_attacks(
        self, transactions: list[GraphTransaction]
    ) -> list[RiskFactor]:
        factors: list[RiskFactor] = []
        dust_txs = []
        for tx in transactions:
            try:
                val = float(tx.value) / 1e18 if tx.value.isdigit() else 0.0
                if 0 < val <= 0.0001:
                    dust_txs.append(tx)
            except Exception:
                continue

        if len(dust_txs) >= 4:
            factors.append(
                RiskFactor(
                    factor_type=RiskFactorType.DUSTING_ATTACK,
                    severity=RiskSeverity.LOW,
                    score=30,
                    weight=RISK_WEIGHTS[RiskFactorType.DUSTING_ATTACK],
                    description=f"Dusting activity: {len(dust_txs)} micro-transactions (<= 0.0001 ETH) detected",
                    evidence={"dust_count": len(dust_txs)},
                    confidence=ConfidenceLevel.PROBABLE,
                )
            )
        return factors

    def _calculate_overall_score(self, factors: list[RiskFactor]) -> float:
        active_factors = [f for f in factors if f.score > 0]
        if not active_factors:
            return 0.0

        total_weighted = sum(f.weighted_score for f in active_factors)
        total_weight = sum(f.weight for f in active_factors)

        if total_weight == 0:
            return 0.0

        base_score = total_weighted / total_weight
        max_possible = max(f.score for f in active_factors)

        return min(base_score * 1.1, max_possible, 100.0)

    def _score_to_severity(self, score: float) -> RiskSeverity:
        for severity, threshold in sorted(SEVERITY_THRESHOLDS.items(), key=lambda x: -x[1]):
            if score >= threshold:
                return severity
        return RiskSeverity.INFO

    def _generate_summary(
        self, factors: list[RiskFactor], score: float, level: RiskSeverity
    ) -> str:
        active_factors = [f for f in factors if f.score > 0]
        if not active_factors:
            return "All 12 risk factors evaluated clean. Wallet appears clean based on current heuristic analysis."

        critical = [f for f in active_factors if f.severity == RiskSeverity.CRITICAL]
        high = [f for f in active_factors if f.severity == RiskSeverity.HIGH]
        medium = [f for f in active_factors if f.severity == RiskSeverity.MEDIUM]

        parts = [f"Overall risk score: {score:.1f}/100 ({level.value.upper()})."]

        if critical:
            parts.append(
                f"{len(critical)} critical factor(s): {', '.join(f.factor_type.value.replace('_', ' ') for f in critical)}."
            )
        if high:
            parts.append(
                f"{len(high)} high-risk factor(s): {', '.join(f.factor_type.value.replace('_', ' ') for f in high)}."
            )
        if medium:
            parts.append(
                f"{len(medium)} medium-risk factor(s): {', '.join(f.factor_type.value.replace('_', ' ') for f in medium)}."
            )

        clean_count = len(factors) - len(active_factors)
        if clean_count > 0:
            parts.append(f"{clean_count} factor(s) evaluated clean (0 pts).")

        return " ".join(parts)

    def _get_methodology(self) -> str:
        return (
            "Risk scoring uses weighted factor analysis with 12 risk factor types. "
            "Each factor has a base score (0-100) and weight reflecting its predictive value for illicit activity. "
            "Overall score is weighted average capped at maximum factor score. "
            "Severity thresholds: CRITICAL>=80, HIGH>=60, MEDIUM>=40, LOW>=20, INFO<20. "
            "Confidence levels indicate evidence quality: CONFIRMED (verified), HIGH_CONFIDENCE (strong heuristic), "
            "PROBABLE (single strong signal), UNKNOWN (insufficient evidence)."
        )


risk_scoring_engine = RiskScoringEngine()
