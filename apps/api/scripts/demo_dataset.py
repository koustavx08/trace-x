#!/usr/bin/env python3
"""
TRACE-X synthetic demo dataset.

This module holds the *data* behind `seed_demo_data.py`: five fictional
investigations, the wallets they touch, and the transaction flows between
them. It deliberately imports nothing from `src`, so the dataset can be built
and validated without a database, a Neo4j instance or any application config:

    python scripts/demo_dataset.py            # build + validate + summary
    python scripts/demo_dataset.py --json     # machine-readable summary

Realism rules this dataset follows (`validate_dataset` enforces most of them):

* Every address is a valid EIP-55 checksummed address. Addresses belonging to
  public infrastructure (exchange hot wallets, mixers, bridges, DEX routers,
  token contracts) are the real, publicly documented mainnet addresses so that
  entity attribution in the demo matches what an analyst would see on-chain.
* Every address belonging to a *suspect* -- attackers, ransomware affiliates,
  launderers, vendors, exchange deposit addresses -- is generated from a fixed
  salt (`synthetic_address`). Those addresses are fictional by construction:
  criminal conduct is never attributed to a real on-chain identity.
* Transaction hashes are 32-byte keccak digests (66 characters, like the real
  thing), derived deterministically so a re-seed reproduces the same graph.
* Block numbers are derived from the transaction timestamp using each chain's
  real block time and a real block-height anchor, so `block_number` and
  `timestamp` agree with each other and with the case's date.
* Values are token-accurate: correct decimals, correct token contract per
  chain, and USD values priced from that token's January-2024 spot price
  rather than a single flat rate.
* Funds are conserved. A wallet cannot send what it never received, transfers
  carry realistic gas costs, and swap/unwrap outputs are tracked so balances
  stay consistent across a whole flow.
* Cross-chain movement is modelled the way it actually happens: a deposit
  transaction to the bridge on the source chain, and a separate mint/withdraw
  transaction from the bridge on the destination chain. A single transaction
  never spans two chains.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from eth_utils import keccak, to_checksum_address

# Marker written into every row/node this dataset produces. The seeder uses it
# to find and delete its own data on a re-run, so nothing else is touched.
SYNTHETIC_MARKER = "SYNTHETIC_DEMO_DATA"

#: Salt for every fictional address and transaction hash. Changing it changes
#: the whole synthetic identity set, so it is versioned rather than tweaked.
_SALT = b"TRACE-X/SIH-2026/synthetic-demo/v2"


def synthetic_address(label: str) -> str:
    """A deterministic, checksummed, *fictional* EVM address for `label`.

    Derived from a salted keccak digest rather than a private key, so it is
    valid in form, stable across runs, and (with overwhelming probability)
    unused on any real chain -- which is the point: the demo attributes crime
    only to addresses that cannot belong to anyone.
    """
    digest = keccak(_SALT + b"|addr|" + label.encode())
    return to_checksum_address("0x" + digest[-20:].hex())


def synthetic_tx_hash(*parts: object) -> str:
    """A deterministic 32-byte transaction hash, formatted like a real one."""
    payload = b"|".join([_SALT, b"tx", *(str(p).encode() for p in parts)])
    return "0x" + keccak(payload).hex()


def _rng(*parts: object) -> random.Random:
    """A deterministic RNG seeded from `parts` (stable across processes)."""
    return random.Random(
        int.from_bytes(keccak(b"|".join(str(p).encode() for p in parts))[:8], "big")
    )


def T(stamp: str) -> datetime:  # noqa: N802 - reads as a literal in flow tables
    """`T("2024-01-13 12:34:07")` -> timezone-aware UTC datetime."""
    return datetime.fromisoformat(stamp).replace(tzinfo=UTC)


# ============================================================
# CHAINS
# ============================================================


@dataclass(frozen=True)
class ChainSpec:
    """Enough of a chain to place a transaction in time and in a block.

    `anchor_block` / `anchor_time` are a real (approximate) height/timestamp
    pair; heights for demo transactions are interpolated from them at the
    chain's average block time. That keeps `block_number` plausible for the
    date shown instead of being an unrelated random integer.
    """

    name: str
    native_symbol: str
    anchor_block: int
    anchor_time: datetime
    block_seconds: float
    gas_price_gwei: tuple[float, float]

    def block_at(self, when: datetime) -> int:
        drift = (when - self.anchor_time).total_seconds() / self.block_seconds
        return self.anchor_block + int(round(drift))


CHAINS: dict[str, ChainSpec] = {
    # Ethereum block 19,000,000 was mined on 2024-01-21; ~12.05s per block.
    "Ethereum": ChainSpec(
        "Ethereum", "ETH", 19_000_000, T("2024-01-21 03:33:00"), 12.05, (14.0, 62.0)
    ),
    "Polygon": ChainSpec(
        "Polygon", "MATIC", 52_000_000, T("2024-01-02 00:00:00"), 2.1, (60.0, 260.0)
    ),
    "Arbitrum": ChainSpec(
        "Arbitrum", "ETH", 168_000_000, T("2024-01-15 00:00:00"), 0.26, (0.01, 0.12)
    ),
    "BSC": ChainSpec("BSC", "BNB", 34_800_000, T("2024-01-14 00:00:00"), 3.0, (1.0, 5.0)),
}


# ============================================================
# TOKENS  (January 2024 spot prices, USD)
# ============================================================


@dataclass(frozen=True)
class TokenSpec:
    symbol: str
    decimals: int
    usd: Decimal
    address: str | None  # None => the chain's native coin


def _token(symbol: str, decimals: int, usd: str, address: str | None) -> TokenSpec:
    return TokenSpec(
        symbol, decimals, Decimal(usd), to_checksum_address(address) if address else None
    )


TOKENS: dict[tuple[str, str], TokenSpec] = {
    ("Ethereum", "ETH"): _token("ETH", 18, "2530.40", None),
    ("Ethereum", "WETH"): _token(
        "WETH", 18, "2530.40", "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    ),
    ("Ethereum", "USDC"): _token("USDC", 6, "1.00", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"),
    ("Ethereum", "USDT"): _token("USDT", 6, "1.00", "0xdac17f958d2ee523a2206206994597c13d831ec7"),
    ("Ethereum", "DAI"): _token("DAI", 18, "1.00", "0x6b175474e89094c44da98b954eedeac495271d0f"),
    ("Polygon", "MATIC"): _token("MATIC", 18, "0.79", None),
    ("Polygon", "WETH"): _token(
        "WETH", 18, "2530.40", "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619"
    ),
    ("Polygon", "USDC"): _token("USDC", 6, "1.00", "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"),
    ("Arbitrum", "ETH"): _token("ETH", 18, "2530.40", None),
    ("Arbitrum", "USDT"): _token("USDT", 6, "1.00", "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9"),
    ("BSC", "BNB"): _token("BNB", 18, "312.60", None),
    ("BSC", "USDT"): _token("USDT", 18, "1.00", "0x55d398326f99059ff775485246999027b3197955"),
}

#: Gas a transaction of each kind burns. Real-world orders of magnitude: a
#: bare native transfer is 21k, an ERC-20 transfer ~45-65k, a DEX swap
#: ~130-220k, a Tornado Cash deposit ~1.1M.
GAS_BY_METHOD: dict[str, int] = {
    "transfer": 21_000,
    "token_transfer": 63_450,
    "sweep": 46_800,
    "swap": 184_300,
    "unwrap": 36_100,
    "deploy": 1_412_600,
    "exploit": 872_400,
    "withdraw": 341_200,
    "mixer_deposit": 1_108_500,
    "mixer_withdraw": 356_900,
    "shield": 632_800,
    "bridge_deposit": 172_400,
    "bridge_mint": 118_900,
    "seizure_transfer": 21_000,
}


# ============================================================
# PUBLIC INFRASTRUCTURE ADDRESS BOOK
# ============================================================
#
# Real, publicly documented mainnet addresses. They are infrastructure, not
# suspects: exchange hot wallets, sanctioned mixer pools, canonical bridges,
# DEX routers and token contracts. Attribution in a real investigation comes
# from exactly this kind of published label set, so the demo uses the real
# values -- an analyst can paste any of them into a block explorer and see the
# same entity. Stored lowercase, checksummed on load.

# fmt: off
INFRASTRUCTURE: dict[str, dict[str, object]] = {
    # --- Centralised exchanges ------------------------------------------
    "binance_hot_14": {"name": "Binance", "type": "exchange", "chain": "Ethereum", "address": "0x28c6c06298d514db089934071355e5743bf21d60", "confidence": "CONFIRMED", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "binance_hot_15": {"name": "Binance", "type": "exchange", "chain": "Ethereum", "address": "0x21a31ee1afc51d94c2ef3caadb94d5c86c1f9e3d", "confidence": "CONFIRMED", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "binance_reserve_eth": {"name": "Binance", "type": "exchange", "chain": "Ethereum", "address": "0xf977814e90da44bfa03b6295a0616a897441acec", "confidence": "CONFIRMED", "source": "exchange_directory", "tags": ["cex", "kyc", "reserve"]},
    "binance_reserve_polygon": {"name": "Binance", "type": "exchange", "chain": "Polygon", "address": "0xf977814e90da44bfa03b6295a0616a897441acec", "confidence": "CONFIRMED", "source": "exchange_directory", "tags": ["cex", "kyc", "reserve"]},
    "binance_hot_bsc": {"name": "Binance", "type": "exchange", "chain": "BSC", "address": "0x8894e0a0c962cb723c1976a4421c95949be2d4e3", "confidence": "CONFIRMED", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "coinbase_1": {"name": "Coinbase", "type": "exchange", "chain": "Ethereum", "address": "0x71660c4005ba85c37ccec55d0c4493e66fe775d3", "confidence": "CONFIRMED", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "coinbase_2": {"name": "Coinbase", "type": "exchange", "chain": "Ethereum", "address": "0x503828976d22510aad0201ac7ec88293211d23da", "confidence": "CONFIRMED", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "kraken_1": {"name": "Kraken", "type": "exchange", "chain": "Ethereum", "address": "0x2910543af39aba0cd09dbb2d50200b3e800a63d2", "confidence": "CONFIRMED", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "kraken_2": {"name": "Kraken", "type": "exchange", "chain": "Ethereum", "address": "0x0a869d79a7052c7f1b55a8ebabaa43105310d4d2", "confidence": "CONFIRMED", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "kraken_4": {"name": "Kraken", "type": "exchange", "chain": "Ethereum", "address": "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0", "confidence": "CONFIRMED", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "okx_1": {"name": "OKX", "type": "exchange", "chain": "Ethereum", "address": "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b", "confidence": "CONFIRMED", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "huobi_1": {"name": "HTX (Huobi)", "type": "exchange", "chain": "Ethereum", "address": "0xab5c66752a9e8167967685f1450532fb96d5d24f", "confidence": "HIGH_CONFIDENCE", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "kucoin_1": {"name": "KuCoin", "type": "exchange", "chain": "Ethereum", "address": "0x2b5634c42055806a59e9107ed44d43c426e58258", "confidence": "HIGH_CONFIDENCE", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "gate_1": {"name": "Gate.io", "type": "exchange", "chain": "Ethereum", "address": "0x0d0707963952f2fba59dd06f2b425ace40b492fe", "confidence": "HIGH_CONFIDENCE", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    "bybit_hot_polygon": {"name": "Bybit", "type": "exchange", "chain": "Polygon", "address": "0xf89d7b9c864f589bbf53a82105107622b35eaa40", "confidence": "HIGH_CONFIDENCE", "source": "exchange_directory", "tags": ["cex", "kyc", "hot_wallet"]},
    # --- Mixers / privacy protocols (OFAC-designated where noted) -------
    "tornado_router": {"name": "Tornado Cash", "type": "mixer", "chain": "Ethereum", "address": "0x722122df12d4e14e13ac3b6895a86e84145b6967", "confidence": "CONFIRMED", "source": "ofac_sdn", "tags": ["mixer", "privacy", "sanctioned", "high_risk"]},
    "tornado_100eth": {"name": "Tornado Cash 100 ETH pool", "type": "mixer", "chain": "Ethereum", "address": "0xa160cdab225685da1d56aa342ad8841c3b53f291", "confidence": "CONFIRMED", "source": "ofac_sdn", "tags": ["mixer", "privacy", "sanctioned", "high_risk"]},
    "tornado_10eth": {"name": "Tornado Cash 10 ETH pool", "type": "mixer", "chain": "Ethereum", "address": "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf", "confidence": "CONFIRMED", "source": "ofac_sdn", "tags": ["mixer", "privacy", "sanctioned", "high_risk"]},
    "tornado_1eth": {"name": "Tornado Cash 1 ETH pool", "type": "mixer", "chain": "Ethereum", "address": "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936", "confidence": "CONFIRMED", "source": "ofac_sdn", "tags": ["mixer", "privacy", "sanctioned", "high_risk"]},
    "railgun_proxy": {"name": "Railgun", "type": "mixer", "chain": "Ethereum", "address": "0xfa7093cdd9ee6932b4eb2c9e1cde7ce00b1fa4b9", "confidence": "HIGH_CONFIDENCE", "source": "privacy_protocol_directory", "tags": ["privacy", "zk", "shielded_pool"]},
    # --- Bridges ---------------------------------------------------------
    "polygon_root_manager": {"name": "Polygon PoS Bridge", "type": "bridge", "chain": "Ethereum", "address": "0xa0c68c638235ee32657e8f720a23cec1bfc77c77", "confidence": "CONFIRMED", "source": "bridge_directory", "tags": ["bridge", "cross_chain"]},
    "polygon_erc20_predicate": {"name": "Polygon PoS Bridge", "type": "bridge", "chain": "Ethereum", "address": "0x40ec5b33f54e0e8a33a975908c5ba1c14e5bbbdf", "confidence": "CONFIRMED", "source": "bridge_directory", "tags": ["bridge", "cross_chain", "erc20_predicate"]},
    "polygon_child_manager": {"name": "Polygon PoS Bridge", "type": "bridge", "chain": "Polygon", "address": "0xa6fa4fb5f76172d178d61b04b0ecd319c5d1c0aa", "confidence": "CONFIRMED", "source": "bridge_directory", "tags": ["bridge", "cross_chain", "child_chain_manager"]},
    "arbitrum_l1_gateway": {"name": "Arbitrum One Bridge", "type": "bridge", "chain": "Ethereum", "address": "0xa3a7b6f88361f48403514059f1f16c8e78d60eec", "confidence": "CONFIRMED", "source": "bridge_directory", "tags": ["bridge", "l2"]},
    "arbitrum_l2_gateway": {"name": "Arbitrum One Bridge", "type": "bridge", "chain": "Arbitrum", "address": "0x09e9222e96e7b4ae2a407b98d48e330053351eee", "confidence": "CONFIRMED", "source": "bridge_directory", "tags": ["bridge", "l2"]},
    "optimism_gateway": {"name": "Optimism Gateway", "type": "bridge", "chain": "Ethereum", "address": "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1", "confidence": "CONFIRMED", "source": "bridge_directory", "tags": ["bridge", "l2"]},
    "stargate_router_eth": {"name": "Stargate Finance", "type": "bridge", "chain": "Ethereum", "address": "0x8731d54e9d02c286767d56ac03e8037c07e01e98", "confidence": "CONFIRMED", "source": "bridge_directory", "tags": ["bridge", "cross_chain", "layerzero"]},
    "stargate_router_bsc": {"name": "Stargate Finance", "type": "bridge", "chain": "BSC", "address": "0x4a364f8c717caad9a442737eb7b8a55cc6cf18d8", "confidence": "CONFIRMED", "source": "bridge_directory", "tags": ["bridge", "cross_chain", "layerzero"]},
    # --- DEX routers / lending -------------------------------------------
    "uniswap_v3_router": {"name": "Uniswap V3", "type": "defi", "chain": "Ethereum", "address": "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45", "confidence": "CONFIRMED", "source": "defi_directory", "tags": ["defi", "dex", "router"]},
    "uniswap_v2_router": {"name": "Uniswap V2", "type": "defi", "chain": "Ethereum", "address": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d", "confidence": "CONFIRMED", "source": "defi_directory", "tags": ["defi", "dex", "router"]},
    "curve_3pool": {"name": "Curve 3pool", "type": "defi", "chain": "Ethereum", "address": "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7", "confidence": "CONFIRMED", "source": "defi_directory", "tags": ["defi", "dex", "stableswap"]},
    "aave_v3_pool": {"name": "Aave V3", "type": "defi", "chain": "Ethereum", "address": "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2", "confidence": "CONFIRMED", "source": "defi_directory", "tags": ["defi", "lending"]},
    "quickswap_router": {"name": "QuickSwap", "type": "defi", "chain": "Polygon", "address": "0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff", "confidence": "CONFIRMED", "source": "defi_directory", "tags": ["defi", "dex", "router"]},
    "pancakeswap_router": {"name": "PancakeSwap V2", "type": "defi", "chain": "BSC", "address": "0x10ed43c718714eb63d5aa57b78b54704e256024e", "confidence": "CONFIRMED", "source": "defi_directory", "tags": ["defi", "dex", "router"]},
    # --- Token contracts --------------------------------------------------
    "weth_contract": {"name": "Wrapped Ether (WETH)", "type": "defi", "chain": "Ethereum", "address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "confidence": "CONFIRMED", "source": "token_registry", "tags": ["token", "wrapped"]},
    "usdc_contract": {"name": "USD Coin (USDC)", "type": "defi", "chain": "Ethereum", "address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "confidence": "CONFIRMED", "source": "token_registry", "tags": ["token", "stablecoin"]},
    "usdt_contract": {"name": "Tether (USDT)", "type": "defi", "chain": "Ethereum", "address": "0xdac17f958d2ee523a2206206994597c13d831ec7", "confidence": "CONFIRMED", "source": "token_registry", "tags": ["token", "stablecoin"]},
    "dai_contract": {"name": "Dai Stablecoin (DAI)", "type": "defi", "chain": "Ethereum", "address": "0x6b175474e89094c44da98b954eedeac495271d0f", "confidence": "CONFIRMED", "source": "token_registry", "tags": ["token", "stablecoin"]},
    "usdc_contract_polygon": {"name": "USD Coin (USDC.e)", "type": "defi", "chain": "Polygon", "address": "0x2791bca1f2de4661ed88a30c99a7a9449aa84174", "confidence": "CONFIRMED", "source": "token_registry", "tags": ["token", "stablecoin"]},
    "usdt_contract_bsc": {"name": "Binance-Peg USDT", "type": "defi", "chain": "BSC", "address": "0x55d398326f99059ff775485246999027b3197955", "confidence": "CONFIRMED", "source": "token_registry", "tags": ["token", "stablecoin"]},
}
# fmt: on


def infra(key: str) -> str:
    """Checksummed address of a known infrastructure entity."""
    return to_checksum_address(str(INFRASTRUCTURE[key]["address"]))


# ============================================================
# DATASET STRUCTURES
# ============================================================


@dataclass
class Wallet:
    """One address, on one chain, as it appears inside one case."""

    key: str
    chain: str
    address: str
    label: str
    attribution: str  # models.AttributionStatus value
    risk: Decimal
    entity_name: str | None = None
    entity_type: str = "unknown"  # graph EntityType value
    entity_confidence: str = "UNKNOWN"  # graph ConfidenceLevel value
    #: True for the fictional actors of the scenario, False for real public
    #: infrastructure. Only synthetic wallets are balance-checked, since an
    #: exchange hot wallet's real balance is not part of this dataset.
    synthetic: bool = True
    note: str | None = None
    #: Holdings the wallet already had when the case window opens. Wallets do
    #: not spring into existence at the first traced hop, and without this a
    #: victim contract could not be drained and a vendor could not post a bond.
    opening: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class Hop:
    """One transaction in a flow, before it is given a hash/block/fee."""

    src: str
    dst: str
    symbol: str
    amount: Decimal
    method: str
    at: datetime
    suspicious: bool = False
    #: Value received back in the same transaction (a DEX swap's output leg, a
    #: WETH unwrap). Recorded in the transaction's metadata as a token
    #: transfer, and credited to the sender when balances are checked.
    out_symbol: str | None = None
    out_amount: Decimal | None = None
    note: str | None = None


@dataclass
class Tx:
    """A materialized transaction: everything the seeder writes."""

    tx_hash: str
    chain: str
    block_number: int
    timestamp: datetime
    from_key: str
    to_key: str
    from_address: str
    to_address: str
    token_symbol: str
    token_address: str | None
    amount: Decimal
    value_units: str
    value_usd: Decimal
    method: str
    is_suspicious: bool
    gas_used: int
    gas_price_wei: int
    fee_native: Decimal
    nonce: int
    note: str | None = None
    token_transfers: list[dict[str, str]] = field(default_factory=list)


@dataclass
class Case:
    case_number: str
    title: str
    crime_type: str  # models.CrimeType value
    status: str  # models.CaseStatus value
    opened_at: datetime
    description: str
    wallets: list[Wallet]
    hops: list[Hop]
    txs: list[Tx] = field(default_factory=list)
    #: Wallet key an analyst would start the trace from.
    primary_key: str = ""
    tags: list[str] = field(default_factory=list)
    #: Narrative facts an analyst would record; surfaced in the case report.
    findings: list[str] = field(default_factory=list)

    @property
    def wallet_by_key(self) -> dict[str, Wallet]:
        return {w.key: w for w in self.wallets}

    @property
    def chains(self) -> list[str]:
        seen = []
        for w in self.wallets:
            if w.chain not in seen:
                seen.append(w.chain)
        return seen


# ============================================================
# WALLET HELPERS
# ============================================================


def actor(
    key: str,
    chain: str,
    label: str,
    risk: str,
    *,
    attribution: str = "under_review",
    entity_name: str | None = None,
    entity_type: str = "unknown",
    entity_confidence: str = "UNKNOWN",
    address: str | None = None,
    opening: dict[str, str] | None = None,
    note: str | None = None,
) -> Wallet:
    """A fictional participant in a scenario (suspect, victim, deposit address)."""
    return Wallet(
        key=key,
        chain=chain,
        address=address or synthetic_address(key),
        label=label,
        attribution=attribution,
        risk=Decimal(risk),
        entity_name=entity_name,
        entity_type=entity_type,
        entity_confidence=entity_confidence,
        synthetic=True,
        note=note,
        opening={sym: Decimal(amt) for sym, amt in (opening or {}).items()},
    )


def known(key: str, risk: str, label: str | None = None, *, as_key: str | None = None) -> Wallet:
    """A real, publicly labelled infrastructure address from `INFRASTRUCTURE`."""
    spec = INFRASTRUCTURE[key]
    return Wallet(
        key=as_key or key,
        chain=str(spec["chain"]),
        address=infra(key),
        label=label or str(spec["name"]),
        attribution="confirmed",
        risk=Decimal(risk),
        entity_name=str(spec["name"]),
        entity_type=str(spec["type"]),
        entity_confidence=str(spec["confidence"]),
        synthetic=False,
    )


def D(value: str | int) -> Decimal:  # noqa: N802 - reads as a literal in flow tables
    return Decimal(str(value))


# ============================================================
# CASE 1 - DeFi oracle-manipulation exploit
# ============================================================


def _case_defi_exploit() -> Case:
    # fmt: off
    wallets = [
        actor("exploit_operator", "Ethereum", "Exploit operator - funding EOA", "96.5", attribution="attributed", entity_confidence="PROBABLE", note="Funded from a Tornado Cash 100 ETH withdrawal 3h12m before the exploit transaction."),
        actor("exploit_operator_polygon", "Polygon", "Exploit operator - same EOA on Polygon", "94.0", attribution="attributed", entity_confidence="PROBABLE", address=synthetic_address("exploit_operator"), note="Same private key reused across chains - the strongest link between the Ethereum and Polygon halves of this trace."),
        actor("exploit_contract", "Ethereum", "Exploit contract (deployed, then self-destructed)", "92.0", attribution="attributed", entity_confidence="HIGH_CONFIDENCE"),
        actor("protocol_pool", "Ethereum", "Protocol X lending pool (victim contract)", "9.0", attribution="confirmed", entity_name="Protocol X", entity_type="defi", entity_confidence="CONFIRMED", opening={"WETH": "41250.6"}, note="Complainant contract. Oracle price feed manipulated within a single block."),
        known("tornado_100eth", "99.0"),
        known("uniswap_v3_router", "8.0"),
        known("weth_contract", "5.0"),
        known("polygon_root_manager", "22.0"),
        known("polygon_child_manager", "22.0"),
        known("quickswap_router", "8.0"),
        actor("kraken_deposit", "Ethereum", "Kraken deposit address (attributed)", "64.0", attribution="attributed", entity_name="Kraken", entity_type="exchange", entity_confidence="HIGH_CONFIDENCE", note="Deposit address, not a hot wallet: swept to Kraken's hot wallet 35 minutes after funding. Subject information requested under MLAT."),
        known("kraken_1", "12.0"),
        actor("binance_deposit_polygon", "Polygon", "Binance deposit address (attributed)", "66.0", attribution="attributed", entity_name="Binance", entity_type="exchange", entity_confidence="HIGH_CONFIDENCE"),
        known("binance_reserve_polygon", "10.0"),
    ]
    # fmt: on

    # fmt: off
    hops = [
        Hop("tornado_100eth", "exploit_operator", "ETH", D("100"), "mixer_withdraw", T("2024-01-13 09:14:23"), True, note="Gas funding withdrawn from the 100 ETH pool."),
        Hop("exploit_operator", "exploit_contract", "ETH", D("0"), "deploy", T("2024-01-13 12:29:41"), True, note="Exploit contract deployment."),
        Hop("protocol_pool", "exploit_contract", "WETH", D("3214.8742"), "exploit", T("2024-01-13 12:33:47"), True, note="Oracle price manipulated inside a flash loan; pool drained in one transaction."),
        Hop("exploit_contract", "exploit_operator", "WETH", D("3214.8742"), "sweep", T("2024-01-13 12:35:11"), True),
        Hop("exploit_operator", "weth_contract", "WETH", D("2014.8742"), "unwrap", T("2024-01-13 12:52:06"), False, out_symbol="ETH", out_amount=D("2014.8742")),
        Hop("exploit_operator", "uniswap_v3_router", "WETH", D("1200"), "swap", T("2024-01-13 13:41:05"), True, out_symbol="USDC", out_amount=D("3033875.64"), note="WETH -> USDC, 0.05% fee tier."),
        Hop("exploit_operator", "tornado_100eth", "ETH", D("100"), "mixer_deposit", T("2024-01-13 13:52:44"), True),
        Hop("exploit_operator", "tornado_100eth", "ETH", D("100"), "mixer_deposit", T("2024-01-13 14:01:19"), True),
        Hop("exploit_operator", "tornado_100eth", "ETH", D("100"), "mixer_deposit", T("2024-01-13 14:09:52"), True),
        Hop("exploit_operator", "tornado_100eth", "ETH", D("100"), "mixer_deposit", T("2024-01-13 14:18:36"), True),
        Hop("exploit_operator", "tornado_100eth", "ETH", D("100"), "mixer_deposit", T("2024-01-13 14:27:11"), True, note="Five identical 100 ETH deposits, 8-9 minutes apart."),
        Hop("exploit_operator", "polygon_root_manager", "ETH", D("900"), "bridge_deposit", T("2024-01-13 14:58:27"), True),
        Hop("polygon_child_manager", "exploit_operator_polygon", "WETH", D("900"), "bridge_mint", T("2024-01-13 15:07:33"), True, note="Polygon-side mint of the bridged ETH, 9m06s after the L1 deposit."),
        Hop("exploit_operator_polygon", "quickswap_router", "WETH", D("900"), "swap", T("2024-01-13 16:02:18"), True, out_symbol="USDC", out_amount=D("2268942.31")),
        Hop("exploit_operator_polygon", "binance_deposit_polygon", "USDC", D("800000.00"), "token_transfer", T("2024-01-13 16:41:52"), True),
        Hop("exploit_operator_polygon", "binance_deposit_polygon", "USDC", D("750000.00"), "token_transfer", T("2024-01-14 03:12:44"), True),
        Hop("exploit_operator_polygon", "binance_deposit_polygon", "USDC", D("718942.31"), "token_transfer", T("2024-01-14 09:58:07"), True, note="Three deposits under the USD 1M internal review threshold."),
        Hop("exploit_operator", "kraken_deposit", "USDC", D("3033875.64"), "token_transfer", T("2024-01-14 07:44:19"), True),
        Hop("kraken_deposit", "kraken_1", "USDC", D("3033875.64"), "sweep", T("2024-01-14 08:19:02"), False, note="Exchange-internal consolidation sweep - confirms the deposit address belongs to Kraken."),
        Hop("binance_deposit_polygon", "binance_reserve_polygon", "USDC", D("2268942.31"), "sweep", T("2024-01-14 11:20:35"), False),
    ]
    # fmt: on

    return Case(
        case_number="TRX-20240115-0042",
        title="DeFi Protocol Flash Loan Exploit - Protocol X",
        crime_type="fraud",
        status="in_progress",
        opened_at=T("2024-01-15 04:35:00"),
        description=(
            "Oracle-manipulation exploit against the Protocol X lending pool on Ethereum. "
            "The operator funded a fresh EOA with a 100 ETH Tornado Cash withdrawal, deployed a "
            "single-use exploit contract and drained 3,214.8742 WETH (USD 8.14M at the January 2024 "
            "spot price) by moving the pool's oracle price inside one flash-loaned transaction. "
            "Proceeds split three ways: 500 ETH back into the Tornado Cash 100 ETH pool in five "
            "identical deposits, 1,200 WETH swapped to USDC on Uniswap V3 and sent to a Kraken "
            "deposit address, and 900 ETH bridged to Polygon, swapped on QuickSwap and placed with "
            "a Binance deposit address in three sub-USD-1M transfers. 714.8742 ETH remains at rest "
            "in the operator wallet. Both exchange deposit addresses were confirmed by their "
            "onward consolidation sweeps. [SYNTHETIC DEMO DATA - not a real investigation]"
        ),
        wallets=wallets,
        hops=hops,
        primary_key="exploit_operator",
        tags=[
            "Oracle Manipulation",
            "Flash Loan",
            "Tornado Cash",
            "Cross-chain",
            "Exchange Off-ramp",
        ],
        findings=[
            "Attacker EOA funded from the Tornado Cash 100 ETH pool 3h12m before the exploit - mixer exposure on the inbound side, not only the outbound.",
            "Same EOA address reused on Polygon, linking the Ethereum and Polygon halves of the trace without relying on bridge timing alone.",
            "Two exchange endpoints confirmed by consolidation sweeps: Kraken (USD 3.03M) and Binance on Polygon (USD 2.27M).",
            "Polygon deposits were split into three transfers of USD 800k / 750k / 718.9k, each under the USD 1M review threshold - structuring indicator.",
            "714.8742 ETH (USD 1.81M) remains unspent in the operator wallet; freeze request pending with the two exchanges.",
        ],
    )


# ============================================================
# CASE 2 - Ransomware affiliate payout
# ============================================================


def _case_ransomware() -> Case:
    # fmt: off
    wallets = [
        actor("victim_treasury", "Ethereum", "Victim organisation treasury (complainant)", "4.0", attribution="confirmed", entity_name="Victim organisation (identity sealed)", entity_confidence="CONFIRMED", opening={"USDT": "1412000.00"}, note="Co-operating complainant; ransom paid under duress on 2024-01-08."),
        actor("ransom_collector", "Ethereum", "Ransom collection wallet - LockBit 3.0 affiliate", "93.5", attribution="attributed", entity_name="LockBit 3.0 affiliate (unidentified)", entity_confidence="HIGH_CONFIDENCE"),
        known("tornado_10eth", "99.0"),
        actor("layer_1", "Ethereum", "Layering wallet 1 of 3", "81.0"),
        actor("layer_2", "Ethereum", "Layering wallet 2 of 3", "79.0"),
        actor("layer_3", "Ethereum", "Layering wallet 3 of 3", "78.0"),
        actor("otc_broker", "Ethereum", "Suspected nested OTC desk", "72.0", attribution="under_review", entity_name="Unregistered OTC desk", entity_type="exchange", entity_confidence="PROBABLE", note="Receives from unrelated victims of the same affiliate; no KYC programme identified."),
        actor("kraken_deposit_a", "Ethereum", "Kraken deposit address (attributed)", "58.0", attribution="attributed", entity_name="Kraken", entity_type="exchange", entity_confidence="HIGH_CONFIDENCE"),
        known("kraken_2", "12.0"),
        known("arbitrum_l1_gateway", "20.0"),
        known("arbitrum_l2_gateway", "20.0"),
        actor("affiliate_arbitrum", "Arbitrum", "Affiliate wallet on Arbitrum", "88.0", attribution="attributed", entity_confidence="PROBABLE"),
        actor("kraken_deposit_b", "Arbitrum", "Kraken deposit address on Arbitrum (attributed)", "56.0", attribution="attributed", entity_name="Kraken", entity_type="exchange", entity_confidence="HIGH_CONFIDENCE"),
        actor("kraken_omnibus_arbitrum", "Arbitrum", "Kraken consolidation wallet on Arbitrum (attributed)", "14.0", attribution="attributed", entity_name="Kraken", entity_type="exchange", entity_confidence="HIGH_CONFIDENCE", note="Sweep destination for Kraken's Arbitrum deposit addresses; attributed from sweep behaviour, not from a published label."),
    ]
    # fmt: on

    # fmt: off
    hops = [
        Hop("victim_treasury", "ransom_collector", "USDT", D("1050000.00"), "token_transfer", T("2024-01-08 18:22:41"), True, note="Ransom payment: USD 1.05M, quoted to the victim as 25 BTC."),
        Hop("tornado_10eth", "ransom_collector", "ETH", D("10"), "mixer_withdraw", T("2024-01-08 19:05:12"), True, note="Gas funding for the layering wallets."),
        Hop("ransom_collector", "layer_1", "USDT", D("419880.00"), "token_transfer", T("2024-01-09 02:14:38"), True),
        Hop("ransom_collector", "layer_2", "USDT", D("314910.00"), "token_transfer", T("2024-01-09 02:31:07"), True),
        Hop("ransom_collector", "layer_3", "USDT", D("315130.00"), "token_transfer", T("2024-01-09 02:47:55"), True, note="40/30/30 split across three fresh wallets within 34 minutes."),
        Hop("layer_1", "otc_broker", "USDT", D("419880.00"), "token_transfer", T("2024-01-09 11:03:26"), True),
        Hop("layer_2", "kraken_deposit_a", "USDT", D("314910.00"), "token_transfer", T("2024-01-10 08:47:13"), True),
        Hop("kraken_deposit_a", "kraken_2", "USDT", D("314910.00"), "sweep", T("2024-01-10 09:12:48"), False),
        Hop("layer_3", "arbitrum_l1_gateway", "USDT", D("315130.00"), "bridge_deposit", T("2024-01-10 15:26:04"), True),
        Hop("arbitrum_l2_gateway", "affiliate_arbitrum", "USDT", D("315130.00"), "bridge_mint", T("2024-01-10 15:41:22"), True),
        Hop("affiliate_arbitrum", "kraken_deposit_b", "USDT", D("199750.00"), "token_transfer", T("2024-01-11 07:19:44"), True),
        Hop("kraken_deposit_b", "kraken_omnibus_arbitrum", "USDT", D("199750.00"), "sweep", T("2024-01-11 07:52:10"), False),
    ]
    # fmt: on

    return Case(
        case_number="TRX-20240114-0038",
        title="Ransomware Payment Tracing - LockBit 3.0 Affiliate",
        crime_type="ransomware",
        status="open",
        opened_at=T("2024-01-14 06:40:00"),
        description=(
            "USD 1.05M ransom paid in USDT on Ethereum by a co-operating complainant on 2024-01-08, "
            "quoted to the victim as 25 BTC. The collection wallet was gas-funded from the Tornado "
            "Cash 10 ETH pool, then split the payment 40/30/30 across three fresh layering wallets "
            "within 34 minutes. Leg 1 (USD 419.9k) went to a suspected nested OTC desk with no "
            "identified KYC programme. Leg 2 (USD 314.9k) reached a Kraken deposit address, "
            "confirmed by the exchange's consolidation sweep 25 minutes later. Leg 3 (USD 315.1k) "
            "was bridged to Arbitrum, where USD 199.75k was cashed out to a second Kraken deposit "
            "address and USD 115.4k remains at rest. The affiliate's Bitcoin-side activity, "
            "including reported Wasabi coinjoin use, sits outside this EVM workspace and is held "
            "by the partner agency. [SYNTHETIC DEMO DATA - not a real investigation]"
        ),
        wallets=wallets,
        hops=hops,
        primary_key="ransom_collector",
        tags=["Ransomware", "LockBit 3.0", "Layering", "Nested OTC", "Arbitrum"],
        findings=[
            "Collection wallet gas-funded from the Tornado Cash 10 ETH pool 43 minutes after the ransom landed.",
            "Payment split 40/30/30 across three same-day wallets - textbook layering, no economic purpose.",
            "Two Kraken deposit addresses confirmed by consolidation sweeps; USD 514.66k total is subject to a preservation request.",
            "USD 419.88k sits with an unregistered OTC desk that also receives from unrelated victims of the same affiliate.",
            "USD 115.38k remains at rest on Arbitrum and is the only balance still under the affiliate's control.",
        ],
    )


# ============================================================
# CASE 3 - Peel chain through nested exchange deposits
# ============================================================

#: Exchanges the peel chain cashes out through, in rotation. Each peel goes to
#: a fresh deposit address; every third one is followed to the exchange's
#: published hot wallet by the consolidation sweep that confirms attribution.
_PEEL_EXCHANGES = [
    ("Binance", "binance_hot_14"),
    ("OKX", "okx_1"),
    ("HTX (Huobi)", "huobi_1"),
    ("Gate.io", "gate_1"),
    ("KuCoin", "kucoin_1"),
    ("Coinbase", "coinbase_2"),
]


def _case_laundering() -> Case:
    rng = _rng("peel-chain", "TRX-20240113-0029")
    chain_length = 18

    # fmt: off
    wallets: list[Wallet] = [
        actor("predicate_source", "Ethereum", "Predicate-offence consolidation wallet", "89.0", attribution="attributed", entity_confidence="HIGH_CONFIDENCE", opening={"USDT": "4182500.00"}, note="Consolidates proceeds from four linked investment-fraud complaints."),
        known("curve_3pool", "6.0"),
    ]
    # fmt: on
    # Hot wallets are appended after the loop, so only exchanges that actually
    # receive a consolidation sweep become nodes: an exchange wallet with no
    # edges is graph clutter, not evidence.
    swept_exchanges: set[str] = set()

    hops: list[Hop] = []
    symbol = "USDT"
    balance = D("4182500.00")
    at = T("2023-12-18 07:12:04")

    hops.append(
        Hop(
            "predicate_source",
            "hop_00",
            symbol,
            balance,
            "token_transfer",
            at,
            True,
            note="Opening of the chain: full consolidated balance forwarded in one transfer.",
        )
    )

    for i in range(chain_length):
        cur = f"hop_{i:02d}"
        wallets.append(
            actor(
                cur,
                "Ethereum",
                f"Peel chain wallet {i + 1:02d} of {chain_length}",
                str(round(84 - i * 0.9, 1)),
                attribution="attributed" if i < 6 else "under_review",
                entity_confidence="PROBABLE",
            )
        )

        # --- the peel: a round-number slice to a fresh exchange deposit ---
        at += timedelta(
            hours=rng.randrange(6, 46), minutes=rng.randrange(0, 60), seconds=rng.randrange(0, 60)
        )
        peel = D(rng.randrange(24, 96) * 500)
        if peel > balance / 4:
            peel = (balance / 10).quantize(D("1000"))
        exch_name, exch_key = _PEEL_EXCHANGES[i % len(_PEEL_EXCHANGES)]
        dep = f"deposit_{i:02d}"
        # Most deposit addresses are proven out by the exchange's own
        # consolidation sweep; three are not, and keep the weaker attribution
        # the evidence actually supports.
        swept = i not in (7, 13, 16)
        wallets.append(
            actor(
                dep,
                "Ethereum",
                f"{exch_name} deposit address (attributed)",
                "57.0",
                attribution="attributed" if swept else "under_review",
                entity_name=exch_name,
                entity_type="exchange",
                entity_confidence="HIGH_CONFIDENCE" if swept else "PROBABLE",
            )
        )
        hops.append(
            Hop(cur, dep, symbol, peel, "token_transfer", at, True, note="Round-value peel.")
        )

        if swept:
            swept_exchanges.add(exch_key)
            hops.append(
                Hop(
                    dep,
                    exch_key,
                    symbol,
                    peel,
                    "sweep",
                    at + timedelta(minutes=rng.randrange(11, 95)),
                    False,
                )
            )

        balance -= peel

        # --- asset hop: stablecoin swapped mid-chain to break naive tracing ---
        if i in (5, 11):
            other = "DAI" if symbol == "USDT" else "USDT"
            swapped = (balance * D("0.9996")).quantize(D("0.01"))
            at += timedelta(minutes=rng.randrange(4, 40), seconds=rng.randrange(0, 60))
            hops.append(
                Hop(
                    cur,
                    "curve_3pool",
                    symbol,
                    balance,
                    "swap",
                    at,
                    True,
                    out_symbol=other,
                    out_amount=swapped,
                    note=f"{symbol} -> {other} on Curve 3pool, 0.04% fee.",
                )
            )
            symbol, balance = other, swapped

        # --- forward the remainder to the next wallet in the chain ---
        at += timedelta(minutes=rng.randrange(6, 45), seconds=rng.randrange(0, 60))
        nxt = f"hop_{i + 1:02d}" if i + 1 < chain_length else "deposit_final"
        hops.append(Hop(cur, nxt, symbol, balance, "token_transfer", at, True))

    wallets.append(
        actor(
            "deposit_final",
            "Ethereum",
            "OKX deposit address (attributed) - terminal off-ramp",
            "61.0",
            attribution="attributed",
            entity_name="OKX",
            entity_type="exchange",
            entity_confidence="HIGH_CONFIDENCE",
        )
    )
    hops.append(
        Hop(
            "deposit_final",
            "okx_1",
            symbol,
            balance,
            "sweep",
            at + timedelta(minutes=rng.randrange(20, 140)),
            False,
        )
    )
    swept_exchanges.add("okx_1")

    wallets.extend(known(key, "12.0") for _, key in _PEEL_EXCHANGES if key in swept_exchanges)

    peeled = sum(
        (
            h.amount
            for h in hops
            if h.method == "token_transfer"
            and h.dst.startswith("deposit_")
            and h.dst != "deposit_final"
        ),
        D(0),
    )
    window = f"{min(h.at for h in hops):%Y-%m-%d} and {max(h.at for h in hops):%Y-%m-%d}"

    return Case(
        case_number="TRX-20240113-0029",
        title="International Money Laundering Ring - Nested Exchange Peel Chain",
        crime_type="money_laundering",
        status="closed",
        opened_at=T("2024-01-13 05:15:00"),
        description=(
            f"USD 4.18M of investment-fraud proceeds from four linked complaints, laundered through "
            f"an {chain_length}-hop peel chain on Ethereum between {window}. Each "
            f"hop shaved a round-number slice (USD 12k-47.5k) into a fresh deposit address at one of "
            f"six exchanges - Binance, OKX, HTX, Gate.io, KuCoin and Coinbase - and forwarded the "
            f"remainder to the next wallet, USD {peeled:,.0f} peeled off in total. The chain switched "
            f"stablecoin twice on Curve 3pool (USDT to DAI and back) to break naive same-asset "
            f"tracing. The terminal balance left the chain through a single OKX deposit address. "
            f"Six deposit addresses were confirmed by consolidation sweeps to the exchanges' "
            f"published hot wallets; disclosure orders were served on all six exchanges and the case "
            f"was closed on 2024-02-09. [SYNTHETIC DEMO DATA - not a real investigation]"
        ),
        wallets=wallets,
        hops=hops,
        primary_key="predicate_source",
        tags=[
            "Peel Chain",
            "Nested Exchanges",
            "Round Amounts",
            "Stablecoin Hopping",
            "Disclosure Orders",
        ],
        findings=[
            f"{chain_length}-hop peel chain: every hop peels a round-number slice and forwards the remainder within 6-45 minutes.",
            f"USD {peeled:,.0f} peeled into {chain_length} single-use exchange deposit addresses across six exchanges.",
            "Two mid-chain stablecoin swaps on Curve 3pool (USDT to DAI to USDT) - asset hopping, no economic purpose.",
            "Six deposit addresses proven out by their consolidation sweeps to published exchange hot wallets.",
            "Terminal balance off-ramped through a single OKX deposit address; disclosure orders served on all six exchanges.",
        ],
    )


# ============================================================
# CASE 4 - Darknet marketplace vendor-bond seizure
# ============================================================


def _case_darknet() -> Case:
    rng = _rng("darknet", "TRX-20240112-0017")
    vendor_count = 26

    # fmt: off
    wallets: list[Wallet] = [
        actor("market_escrow", "Ethereum", "Marketplace vendor-bond escrow (seized)", "87.0", attribution="confirmed", entity_name="Darknet marketplace (Hydra successor)", entity_type="darknet", entity_confidence="HIGH_CONFIDENCE"),
        known("polygon_root_manager", "22.0"),
        known("polygon_child_manager", "22.0"),
        known("quickswap_router", "8.0"),
        known("bybit_hot_polygon", "12.0"),
        actor("market_treasury", "Polygon", "Marketplace operator treasury on Polygon", "84.0", attribution="attributed", entity_name="Darknet marketplace (Hydra successor)", entity_type="darknet", entity_confidence="HIGH_CONFIDENCE"),
        actor("bybit_deposit", "Polygon", "Bybit deposit address (attributed)", "63.0", attribution="attributed", entity_name="Bybit", entity_type="exchange", entity_confidence="HIGH_CONFIDENCE"),
        actor("le_custody", "Ethereum", "Law-enforcement custody wallet (seizure order TRX-SZ-2024-0007)", "0.0", attribution="confirmed", entity_name="TRACE-X seized-asset custody", entity_confidence="CONFIRMED", note="Destination of the residual escrow balance after key material was recovered from the seized server."),
    ]
    # fmt: on

    hops: list[Hop] = []
    at = T("2023-12-05 08:41:12")
    total_bonds = D(0)
    for i in range(vendor_count):
        key = f"vendor_{i:02d}"
        bond = (D(rng.randrange(50, 361)) / 20).quantize(D("0.01"))  # 2.50 - 18.00 ETH
        wallets.append(
            actor(
                key,
                "Ethereum",
                f"Vendor bond wallet {i + 1:02d}",
                str(round(58 + rng.random() * 17, 1)),
                attribution="under_review",
                entity_confidence="PROBABLE",
                opening={"ETH": str(bond + D("0.4"))},
            )
        )
        at += timedelta(
            hours=rng.randrange(4, 44), minutes=rng.randrange(0, 60), seconds=rng.randrange(0, 60)
        )
        hops.append(
            Hop(
                key,
                "market_escrow",
                "ETH",
                bond,
                "transfer",
                at,
                True,
                note="Vendor bond posted to the marketplace escrow.",
            )
        )
        total_bonds += bond

    bridged = (total_bonds * D("0.6")).quantize(D("0.0001"))
    residual = total_bonds - bridged

    at = T("2024-01-07 03:22:47")
    hops.append(
        Hop(
            "market_escrow",
            "polygon_root_manager",
            "ETH",
            bridged,
            "bridge_deposit",
            at,
            True,
            note="60% of the escrow balance bridged to Polygon for operator payouts.",
        )
    )
    hops.append(
        Hop(
            "polygon_child_manager",
            "market_treasury",
            "WETH",
            bridged,
            "bridge_mint",
            at + timedelta(minutes=8, seconds=51),
            True,
        )
    )

    swapped = (bridged * D("2530.40") * D("0.9965")).quantize(D("0.01"))
    hops.append(
        Hop(
            "market_treasury",
            "quickswap_router",
            "WETH",
            bridged,
            "swap",
            T("2024-01-07 09:14:38"),
            True,
            out_symbol="USDC",
            out_amount=swapped,
        )
    )

    first_leg = (swapped / 2).quantize(D("0.01"))
    hops.append(
        Hop(
            "market_treasury",
            "bybit_deposit",
            "USDC",
            first_leg,
            "token_transfer",
            T("2024-01-08 12:06:19"),
            True,
        )
    )
    hops.append(
        Hop(
            "market_treasury",
            "bybit_deposit",
            "USDC",
            swapped - first_leg,
            "token_transfer",
            T("2024-01-09 04:47:52"),
            True,
        )
    )
    hops.append(
        Hop(
            "bybit_deposit",
            "bybit_hot_polygon",
            "USDC",
            swapped,
            "sweep",
            T("2024-01-09 05:31:08"),
            False,
        )
    )
    hops.append(
        Hop(
            "market_escrow",
            "le_custody",
            "ETH",
            residual,
            "seizure_transfer",
            T("2024-01-12 09:05:33"),
            False,
            note="Residual escrow balance moved to custody under seizure order TRX-SZ-2024-0007.",
        )
    )

    return Case(
        case_number="TRX-20240112-0017",
        title="Darknet Market Seizure - Vendor Bond Escrow",
        crime_type="darknet_market",
        status="archived",
        opened_at=T("2024-01-12 07:20:00"),
        description=(
            f"EVM-side asset trace supporting the seizure of a Hydra-successor marketplace. The "
            f"marketplace settled in Bitcoin and Monero, but held vendor bonds in ETH: this "
            f"workspace covers the {vendor_count} vendor-bond wallets in scope for the EVM trace "
            f"(out of 150+ vendor accounts in the wider seizure), which posted {total_bonds:.2f} ETH "
            f"to a single escrow contract between 2023-12-05 and 2024-01-06. On 2024-01-07 the "
            f"operator bridged {bridged:.2f} ETH to Polygon, swapped it to USDC on QuickSwap and "
            f"moved it to a Bybit deposit address in two transfers, confirmed by Bybit's "
            f"consolidation sweep. The residual {residual:.2f} ETH was moved to law-enforcement "
            f"custody on 2024-01-12 after key material was recovered from the seized infrastructure. "
            f"Case archived following forfeiture. [SYNTHETIC DEMO DATA - not a real investigation]"
        ),
        wallets=wallets,
        hops=hops,
        primary_key="market_escrow",
        tags=["Darknet Market", "Vendor Bonds", "Seizure", "Polygon Bridge", "Forfeiture"],
        findings=[
            f"{vendor_count} vendor-bond wallets funded one escrow contract over five weeks - {total_bonds:.2f} ETH in total.",
            f"{bridged:.2f} ETH bridged to Polygon and swapped to USDC within six hours of leaving the escrow.",
            "Bybit deposit address confirmed by its consolidation sweep; disclosure order returned two matching vendor identities.",
            f"Residual {residual:.2f} ETH secured in the custody wallet under seizure order TRX-SZ-2024-0007.",
            "Bitcoin and Monero settlement legs are out of EVM scope and held by the partner agency.",
        ],
    )


# ============================================================
# CASE 5 - Sanctions evasion
# ============================================================


def _case_sanctions() -> Case:
    rng = _rng("sanctions", "TRX-20240111-0009")

    # fmt: off
    wallets = [
        actor("legacy_holdings", "Ethereum", "Pre-designation holdings wallet (2019 vintage)", "84.0", attribution="attributed", entity_confidence="HIGH_CONFIDENCE", opening={"ETH": "19800"}, note="Dormant since 2021; reactivated four days after the SDN designation."),
        actor("sdn_primary", "Ethereum", "Designated individual - primary wallet", "99.0", attribution="confirmed", entity_name="OFAC SDN listing (synthetic)", entity_type="sanctioned", entity_confidence="CONFIRMED"),
        known("tornado_100eth", "99.0"),
        known("railgun_proxy", "95.0"),
        known("uniswap_v3_router", "8.0"),
        known("stargate_router_eth", "24.0"),
        known("stargate_router_bsc", "24.0"),
        actor("evader_bsc", "BSC", "Designated individual - BSC wallet", "97.0", attribution="attributed", entity_confidence="HIGH_CONFIDENCE"),
        actor("binance_deposit_bsc", "BSC", "Binance deposit address (attributed)", "68.0", attribution="attributed", entity_name="Binance", entity_type="exchange", entity_confidence="HIGH_CONFIDENCE"),
        known("binance_hot_bsc", "12.0"),
    ]
    # fmt: on

    # fmt: off
    hops = [
        Hop("legacy_holdings", "sdn_primary", "ETH", D("19800"), "transfer", T("2023-12-28 04:31:17"), True, note="Full reactivation of a dormant pre-designation balance: USD 50.10M."),
    ]
    # fmt: on

    at = T("2024-01-04 08:12:00")
    for _ in range(12):
        at += timedelta(
            hours=rng.randrange(2, 11), minutes=rng.randrange(0, 60), seconds=rng.randrange(0, 60)
        )
        hops.append(
            Hop("sdn_primary", "tornado_100eth", "ETH", D("100"), "mixer_deposit", at, True)
        )

    # fmt: off
    hops += [
        Hop("sdn_primary", "railgun_proxy", "ETH", D("6500"), "shield", T("2024-01-07 11:20:03"), True, note="Shielded into Railgun; the shielded balance is not traceable on-chain beyond this point."),
        Hop("sdn_primary", "uniswap_v3_router", "ETH", D("4000"), "swap", T("2024-01-08 09:14:55"), True, out_symbol="USDT", out_amount=D("10102340.00"), note="ETH -> USDT ahead of the cross-chain move."),
        Hop("sdn_primary", "stargate_router_eth", "USDT", D("10102340.00"), "bridge_deposit", T("2024-01-08 10:02:41"), True),
        Hop("stargate_router_bsc", "evader_bsc", "USDT", D("10087186.49"), "bridge_mint", T("2024-01-08 10:09:58"), True, note="Stargate delivered USD 10.09M on BSC, net of the 0.15% protocol fee."),
        Hop("evader_bsc", "binance_deposit_bsc", "USDT", D("3500000.00"), "token_transfer", T("2024-01-08 14:37:26"), True),
        Hop("evader_bsc", "binance_deposit_bsc", "USDT", D("3500000.00"), "token_transfer", T("2024-01-09 06:18:44"), True),
        Hop("evader_bsc", "binance_deposit_bsc", "USDT", D("3087186.49"), "token_transfer", T("2024-01-09 19:52:03"), True),
        Hop("binance_deposit_bsc", "binance_hot_bsc", "USDT", D("10087186.49"), "sweep", T("2024-01-10 02:14:09"), False),
    ]
    # fmt: on

    return Case(
        case_number="TRX-20240111-0009",
        title="Sanctions Evasion - Designated Individual, Mixer and Bridge Layering",
        crime_type="sanctions_evasion",
        status="in_progress",
        opened_at=T("2024-01-11 09:05:00"),
        description=(
            "An OFAC SDN-designated individual reactivated a dormant 2019-vintage wallet four days "
            "after designation and moved 19,800 ETH (USD 50.10M at the January 2024 spot price) into "
            "a fresh primary wallet. Disposal ran on three tracks: 1,200 ETH into the Tornado Cash "
            "100 ETH pool as twelve identical deposits over three days; 6,500 ETH shielded into "
            "Railgun, where the balance stops being traceable on-chain; and 4,000 ETH swapped to "
            "USDT on Uniswap V3 and bridged to BSC via Stargate, arriving as USD 10.09M net of the "
            "0.15% protocol fee. The BSC balance was placed with a single Binance deposit address in "
            "three transfers and swept to Binance's BSC hot wallet. 8,100 ETH (USD 20.50M) remains "
            "at rest in the primary wallet. Blocking notice served on Binance; Railgun-shielded "
            "balance referred for off-chain enquiry. [SYNTHETIC DEMO DATA - not a real investigation]"
        ),
        wallets=wallets,
        hops=hops,
        primary_key="sdn_primary",
        tags=["Sanctions", "OFAC SDN", "Tornado Cash", "Railgun", "Stargate", "BSC"],
        findings=[
            "Dormant pre-designation wallet reactivated four days after the SDN listing - the clearest evidence of intent in the case.",
            "Twelve identical 100 ETH Tornado Cash deposits (USD 3.04M) across three days.",
            "6,500 ETH (USD 16.45M) shielded into Railgun; on-chain tracing ends at the shield transaction.",
            "USD 10.09M bridged to BSC via Stargate and placed with one Binance deposit address in three transfers; blocking notice served.",
            "8,100 ETH (USD 20.50M) still at rest in the primary wallet and subject to the blocking order.",
        ],
    )


CASE_BUILDERS = [
    _case_defi_exploit,
    _case_ransomware,
    _case_laundering,
    _case_darknet,
    _case_sanctions,
]


# ============================================================
# MATERIALIZATION
# ============================================================

#: Native-coin float every synthetic wallet is assumed to hold for gas. Real
#: wallets are funded with a little gas before they can move anything; the
#: dataset does not model those dust transfers as traced hops, so the balance
#: check credits them instead of reporting a false overdraft.
_GAS_FLOAT: dict[str, Decimal] = {
    "Ethereum": Decimal("0.45"),
    "Polygon": Decimal("120"),
    "Arbitrum": Decimal("0.08"),
    "BSC": Decimal("0.35"),
}


def _units(amount: Decimal, decimals: int) -> str:
    """Token amount -> base units, the way an RPC node reports `value`."""
    return str(int((amount * (10**decimals)).to_integral_value()))


def _materialize(case: Case) -> None:
    """Give every hop a hash, a block, a fee and a nonce."""
    by_key = case.wallet_by_key
    case.hops.sort(key=lambda h: h.at)
    nonces: dict[tuple[str, str], int] = {}
    txs: list[Tx] = []

    for index, hop in enumerate(case.hops):
        src, dst = by_key[hop.src], by_key[hop.dst]
        chain_spec = CHAINS[src.chain]
        token = TOKENS[(src.chain, hop.symbol)]

        tx_hash = synthetic_tx_hash(
            case.case_number, index, src.address, dst.address, hop.symbol, hop.amount
        )
        rng = _rng(tx_hash)
        low, high = chain_spec.gas_price_gwei
        gas_price_wei = int(Decimal(str(round(rng.uniform(low, high), 3))) * 10**9)
        gas_used = GAS_BY_METHOD[hop.method]

        nonce_key = (src.chain, src.address)
        if nonce_key not in nonces:
            # Infrastructure contracts have long histories; a suspect's fresh
            # EOA starts at zero. A nonce of 0 on a wallet holding millions is
            # itself a finding, so it should not be faked away.
            nonces[nonce_key] = 0 if src.synthetic else rng.randrange(180_000, 4_200_000)
        nonce = nonces[nonce_key]
        nonces[nonce_key] += 1

        transfers: list[dict[str, str]] = []
        if hop.out_symbol and hop.out_amount is not None:
            out_token = TOKENS[(src.chain, hop.out_symbol)]
            transfers.append(
                {
                    "token_symbol": hop.out_symbol,
                    "token_address": out_token.address or "",
                    "amount": f"{hop.out_amount}",
                    "value": _units(hop.out_amount, out_token.decimals),
                    "to_address": src.address,
                    "value_usd": f"{(hop.out_amount * out_token.usd).quantize(Decimal('0.01'))}",
                    "direction": "output_leg",
                }
            )

        txs.append(
            Tx(
                tx_hash=tx_hash,
                chain=src.chain,
                block_number=chain_spec.block_at(hop.at),
                timestamp=hop.at,
                from_key=hop.src,
                to_key=hop.dst,
                from_address=src.address,
                to_address=dst.address,
                token_symbol=hop.symbol,
                token_address=token.address,
                amount=hop.amount,
                value_units=_units(hop.amount, token.decimals),
                value_usd=(hop.amount * token.usd).quantize(Decimal("0.01")),
                method=hop.method,
                is_suspicious=hop.suspicious,
                gas_used=gas_used,
                gas_price_wei=gas_price_wei,
                fee_native=(Decimal(gas_used * gas_price_wei) / 10**18).quantize(
                    Decimal("0.000000001")
                ),
                nonce=nonce,
                note=hop.note,
                token_transfers=transfers,
            )
        )

    case.txs = txs


def build_cases() -> list[Case]:
    """Build every demo case, materialized and sorted by case number."""
    cases = [build() for build in CASE_BUILDERS]
    for case in cases:
        _materialize(case)
    return cases


# ============================================================
# VALIDATION
# ============================================================


def validate_cases(cases: list[Case]) -> list[str]:
    """Return every realism/consistency problem found in the dataset.

    Cheap to run and worth running: it is what stops the demo from shipping a
    wallet that spends money it never received, a transaction that spans two
    chains, a duplicated hash or an address with a broken checksum.
    """
    problems: list[str] = []
    seen_hashes: dict[str, str] = {}
    identity: dict[tuple[str, str], tuple[str | None, str]] = {}

    for case in cases:
        by_key = case.wallet_by_key
        tag = case.case_number

        for wallet in case.wallets:
            if wallet.chain not in CHAINS:
                problems.append(f"{tag}: wallet {wallet.key} on unknown chain {wallet.chain}")
            try:
                if to_checksum_address(wallet.address) != wallet.address:
                    problems.append(
                        f"{tag}: wallet {wallet.key} address is not EIP-55 checksummed: {wallet.address}"
                    )
            except ValueError:
                problems.append(
                    f"{tag}: wallet {wallet.key} has a malformed address: {wallet.address}"
                )
                continue

            # The same address on the same chain must mean the same thing in
            # every case -- an entity that is "Kraken" in one case and an
            # unknown suspect in another destroys attribution in the graph,
            # where both cases share a single node.
            ident = (wallet.chain, wallet.address.lower())
            claim = (wallet.entity_name, wallet.entity_type)
            if ident in identity and identity[ident] != claim:
                problems.append(
                    f"{tag}: {wallet.address} on {wallet.chain} is attributed as {claim} here but {identity[ident]} elsewhere"
                )
            identity[ident] = claim

        for tx in case.txs:
            if tx.tx_hash in seen_hashes:
                problems.append(
                    f"{tag}: duplicate tx hash {tx.tx_hash} (also in {seen_hashes[tx.tx_hash]})"
                )
            seen_hashes[tx.tx_hash] = tag
            if len(tx.tx_hash) != 66:
                problems.append(
                    f"{tag}: tx hash {tx.tx_hash} is {len(tx.tx_hash)} chars, expected 66"
                )
            src, dst = by_key[tx.from_key], by_key[tx.to_key]
            if src.chain != dst.chain:
                problems.append(
                    f"{tag}: tx {tx.tx_hash[:12]} spans {src.chain} -> {dst.chain}; a cross-chain move needs a deposit tx and a separate mint tx"
                )
            if tx.amount > 0 and tx.value_usd <= 0:
                problems.append(
                    f"{tag}: tx {tx.tx_hash[:12]} moves {tx.amount} {tx.token_symbol} but is priced at USD {tx.value_usd}"
                )
            if tx.block_number <= 0:
                problems.append(f"{tag}: tx {tx.tx_hash[:12]} has a non-positive block number")

        # Block heights must advance with time on each chain.
        for chain in {tx.chain for tx in case.txs}:
            ordered = [tx for tx in case.txs if tx.chain == chain]
            heights = [tx.block_number for tx in ordered]
            if heights != sorted(heights):
                problems.append(
                    f"{tag}: block numbers on {chain} do not follow the transaction timestamps"
                )

        # Funds conservation for the fictional participants.
        balances: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        for wallet in case.wallets:
            if not wallet.synthetic:
                continue
            native = CHAINS[wallet.chain].native_symbol
            balances[(wallet.key, native)] += _GAS_FLOAT[wallet.chain]
            for symbol, amount in wallet.opening.items():
                balances[(wallet.key, symbol)] += amount

        for tx in case.txs:
            src, dst = by_key[tx.from_key], by_key[tx.to_key]
            if src.synthetic:
                balances[(src.key, tx.token_symbol)] -= tx.amount
                balances[(src.key, CHAINS[src.chain].native_symbol)] -= tx.fee_native
                for leg in tx.token_transfers:
                    balances[(src.key, leg["token_symbol"])] += Decimal(leg["amount"])
            if dst.synthetic:
                balances[(dst.key, tx.token_symbol)] += tx.amount

        for (key, symbol), amount in sorted(balances.items()):
            if amount < 0:
                problems.append(
                    f"{tag}: {key} ends {-amount} {symbol} overdrawn - it spends more than it ever received"
                )

    return problems


def build_dataset(*, strict: bool = True) -> list[Case]:
    """Build and validate the demo cases. Raises on any inconsistency."""
    cases = build_cases()
    problems = validate_cases(cases)
    if problems and strict:
        raise ValueError(
            "synthetic demo dataset failed validation:\n  - " + "\n  - ".join(problems)
        )
    return cases


# ============================================================
# DERIVED VIEWS  (used by the seeder)
# ============================================================


@dataclass
class Activity:
    """Everything the demo knows about one address on one chain."""

    chain: str
    address: str
    first_seen: datetime
    last_seen: datetime
    sent_usd: Decimal = Decimal(0)
    received_usd: Decimal = Decimal(0)
    tx_count: int = 0
    cases: list[str] = field(default_factory=list)
    #: False until the address is seen in a transaction, so the case-window
    #: placeholder dates do not survive as a first/last-seen claim.
    seen: bool = False


def wallet_activity(cases: list[Case]) -> dict[tuple[str, str], Activity]:
    """Per-address totals derived from the transactions actually seeded.

    Graph node counters come from here rather than from `random.randint`, so a
    wallet's `tx_count` and volume match the edges an analyst can click on.
    """
    activity: dict[tuple[str, str], Activity] = {}

    for case in cases:
        by_key = case.wallet_by_key
        for wallet in case.wallets:
            ident = (wallet.chain, wallet.address)
            entry = activity.get(ident)
            if entry is None:
                # Seeded with the case window; both ends are pulled back to the
                # real first/last transaction below. A wallet that never
                # transacts keeps the case dates rather than a null.
                entry = activity[ident] = Activity(
                    wallet.chain, wallet.address, case.opened_at, case.opened_at, seen=False
                )
            if case.case_number not in entry.cases:
                entry.cases.append(case.case_number)

        for tx in case.txs:
            for key, is_sender in ((tx.from_key, True), (tx.to_key, False)):
                wallet = by_key[key]
                entry = activity[(wallet.chain, wallet.address)]
                if not entry.seen:
                    entry.first_seen = entry.last_seen = tx.timestamp
                    entry.seen = True
                entry.first_seen = min(entry.first_seen, tx.timestamp)
                entry.last_seen = max(entry.last_seen, tx.timestamp)
                entry.tx_count += 1
                if is_sender:
                    entry.sent_usd += tx.value_usd
                else:
                    entry.received_usd += tx.value_usd

    return activity


def entity_catalogue(cases: list[Case]) -> list[dict[str, object]]:
    """Entity intelligence records: the public address book plus every
    attributed address the cases themselves establish."""
    records: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()

    for spec in INFRASTRUCTURE.values():
        address = to_checksum_address(str(spec["address"]))
        ident = (str(spec["chain"]), address.lower())
        if ident in seen:
            continue
        seen.add(ident)
        records.append(
            {
                "name": spec["name"],
                "entity_type": spec["type"],
                "address": address,
                "chain": spec["chain"],
                "confidence": spec["confidence"],
                "source": spec["source"],
                "tags": list(spec["tags"]),  # type: ignore[arg-type]
            }
        )

    for case in cases:
        for wallet in case.wallets:
            if not wallet.entity_name or wallet.entity_type == "unknown":
                continue
            ident = (wallet.chain, wallet.address.lower())
            if ident in seen:
                continue
            seen.add(ident)
            records.append(
                {
                    "name": wallet.entity_name,
                    "entity_type": wallet.entity_type,
                    "address": wallet.address,
                    "chain": wallet.chain,
                    "confidence": wallet.entity_confidence,
                    "source": "case_attribution",
                    "tags": ["case_derived", case.case_number],
                }
            )

    return records


def case_summary(case: Case) -> dict[str, object]:
    """The headline numbers for one case (also used to keep the web demo page
    in step with what the seeder actually writes)."""
    primary = case.wallet_by_key[case.primary_key]
    endpoints = sorted(
        {w.entity_name for w in case.wallets if w.entity_type == "exchange" and w.entity_name}
    )
    mixer_txs = [
        tx
        for tx in case.txs
        if case.wallet_by_key[tx.to_key].entity_type == "mixer"
        or case.wallet_by_key[tx.from_key].entity_type == "mixer"
    ]
    return {
        "case_number": case.case_number,
        "title": case.title,
        "crime_type": case.crime_type,
        "status": case.status,
        "opened_at": case.opened_at.isoformat(),
        "chains": case.chains,
        "tags": case.tags,
        "wallet_count": len(case.wallets),
        "transaction_count": len(case.txs),
        "suspicious_count": sum(1 for tx in case.txs if tx.is_suspicious),
        "traced_flow_usd": float(sum((tx.value_usd for tx in case.txs), Decimal(0))),
        "largest_tx_usd": float(max(tx.value_usd for tx in case.txs)),
        "primary_wallet": primary.address,
        "primary_chain": primary.chain,
        # The headline score is the wallet the analyst is actually chasing.
        # Taking the maximum instead would report the sanctioned mixer pool's
        # 99 on every case that so much as touches Tornado Cash.
        "risk_score": float(primary.risk),
        "max_wallet_risk": float(max(w.risk for w in case.wallets)),
        "vasp_endpoints": endpoints,
        "mixer_transactions": len(mixer_txs),
        "first_tx": case.txs[0].timestamp.isoformat(),
        "last_tx": case.txs[-1].timestamp.isoformat(),
        "findings": case.findings,
    }


# ============================================================
# CLI
# ============================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build, validate and describe the TRACE-X synthetic demo dataset."
    )
    parser.add_argument("--json", action="store_true", help="print the per-case summary as JSON")
    args = parser.parse_args()

    cases = build_cases()
    problems = validate_cases(cases)
    summaries = [case_summary(case) for case in cases]

    if args.json:
        print(json.dumps({"cases": summaries, "problems": problems}, indent=2))
        return 1 if problems else 0

    print("=" * 78)
    print("TRACE-X synthetic demo dataset")
    print("=" * 78)
    for summary in summaries:
        print(f"\n{summary['case_number']}  {summary['title']}")
        print(f"  status={summary['status']}  chains={', '.join(summary['chains'])}")  # type: ignore[arg-type]
        print(
            f"  wallets={summary['wallet_count']}  transactions={summary['transaction_count']} ({summary['suspicious_count']} suspicious)  mixer txs={summary['mixer_transactions']}"
        )
        print(
            f"  aggregate flow=USD {summary['traced_flow_usd']:,.2f}  largest single tx=USD {summary['largest_tx_usd']:,.2f}"
        )
        print(f"  window={str(summary['first_tx'])[:16]} -> {str(summary['last_tx'])[:16]}")
        print(f"  primary wallet={summary['primary_wallet']} ({summary['primary_chain']})")
        print(f"  exchange endpoints={', '.join(summary['vasp_endpoints']) or 'none'}")  # type: ignore[arg-type]

    activity = wallet_activity(cases)
    entities = entity_catalogue(cases)
    print("\n" + "-" * 78)
    print(
        f"{len(cases)} cases, {sum(len(c.wallets) for c in cases)} case-wallets, {len(activity)} distinct addresses, {sum(len(c.txs) for c in cases)} transactions, {len(entities)} entity records"
    )

    if problems:
        print("\nVALIDATION FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(
        "Validation passed: checksums, chains, hashes, block ordering, attribution and balances all consistent."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
