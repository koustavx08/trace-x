#!/usr/bin/env python3
"""
seed_complex_fraud.py
=====================

Seeds the Neo4j graph with a **production-grade, multi-layered fraud scenario**
that demonstrates all six laundering patterns TRACE-X can detect:

  1. **Smurfing (Fan-Out)**        – $500k split into 10 × $50k sub-threshold txns
  2. **Peel Chain**                – sequential hops peeling off $5-15k to VASPs
  3. **Cross-Chain Bridge Hop**    – ETH → TRON via bridge contract
  4. **Mixer / Tumbler**           – Tornado-Cash-style deposit/withdraw cycle
  5. **Cyclic Wash-Trade**         – 5-node ring returning funds to origin
  6. **Exchange Exit Ramp**        – final off-ramp to identified exchange wallets

The scenario models a real-world **task-scam syndicate** that defrauds victims
via a fake investment app, collects funds in a consolidation wallet, then
launders $500,000 through all six techniques over 72 hours.

Usage:
    cd /home/babu/SIH/trace-x/apps/api
    python scripts/seed_complex_fraud.py

All nodes carry ``SYNTHETIC_DEMO_COMPLEX_FRAUD`` in their metadata so that
re-running the script is idempotent (prior data is deleted first).
"""

import asyncio
import hashlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path – same approach as seed_demo_data.py
# ---------------------------------------------------------------------------
API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.config import get_settings
from src.graph.client import Neo4jClient
from src.graph.models import (
    ConfidenceLevel,
    EntityType,
    GraphEntity,
    GraphTransaction,
    GraphWallet,
)
from src.graph.repository import graph_repository
from src.models import (
    AttributionStatus,
    Case,
    CaseStatus,
    CrimeType,
    InvestigationRun,
    InvestigationStatus,
    Report,
    Transaction,
    User,
    Wallet,
)

settings = get_settings()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SYNTHETIC_MARKER = "SYNTHETIC_DEMO_COMPLEX_FRAUD"


# Realistic-looking addresses (deterministic from label so re-runs are stable)
def _eth_addr(label: str) -> str:
    """Generate a deterministic Ethereum-style address from a human label."""
    h = hashlib.sha256(label.encode()).hexdigest()[:40]
    return f"0x{h}"


def _tron_addr(label: str) -> str:
    """Generate a deterministic TRON-style address from a human label."""
    h = hashlib.sha256(label.encode()).hexdigest()[:33]
    return f"T{h}"


def _btc_addr(label: str) -> str:
    """Generate a deterministic Bitcoin-style address from a human label."""
    h = hashlib.sha256(label.encode()).hexdigest()[:32]
    return f"bc1q{h}"


def _tx_hash(label: str) -> str:
    """Deterministic tx hash."""
    return hashlib.sha256(f"tx-{label}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Scenario timeline
# ---------------------------------------------------------------------------
T0 = datetime(2026, 9, 10, 6, 0, 0, tzinfo=UTC)  # scenario start

# ---------------------------------------------------------------------------
# Wallet catalogue
# ---------------------------------------------------------------------------
# fmt: off
WALLETS: list[dict] = [
    # ── LAYER 0: Victim collection ──────────────────────────────────────
    {"key": "victim_pool",       "chain": "Ethereum", "label": "Victim Pool Consolidator",      "risk": 98, "addr_fn": _eth_addr, "entity_name": "Task-Scam Syndicate",   "entity_type": EntityType.SANCTIONED,  "confidence": ConfidenceLevel.CONFIRMED},

    # ── LAYER 1: Smurfing (fan-out) ─────────────────────────────────────
    {"key": "smurf_01",          "chain": "Ethereum", "label": "Smurf Mule 01",                 "risk": 82, "addr_fn": _eth_addr},
    {"key": "smurf_02",          "chain": "Ethereum", "label": "Smurf Mule 02",                 "risk": 80, "addr_fn": _eth_addr},
    {"key": "smurf_03",          "chain": "Ethereum", "label": "Smurf Mule 03",                 "risk": 78, "addr_fn": _eth_addr},
    {"key": "smurf_04",          "chain": "Ethereum", "label": "Smurf Mule 04",                 "risk": 76, "addr_fn": _eth_addr},
    {"key": "smurf_05",          "chain": "Ethereum", "label": "Smurf Mule 05",                 "risk": 74, "addr_fn": _eth_addr},
    {"key": "smurf_06",          "chain": "Ethereum", "label": "Smurf Mule 06",                 "risk": 72, "addr_fn": _eth_addr},
    {"key": "smurf_07",          "chain": "Ethereum", "label": "Smurf Mule 07",                 "risk": 70, "addr_fn": _eth_addr},
    {"key": "smurf_08",          "chain": "Ethereum", "label": "Smurf Mule 08",                 "risk": 68, "addr_fn": _eth_addr},
    {"key": "smurf_09",          "chain": "Ethereum", "label": "Smurf Mule 09",                 "risk": 66, "addr_fn": _eth_addr},
    {"key": "smurf_10",          "chain": "Ethereum", "label": "Smurf Mule 10",                 "risk": 64, "addr_fn": _eth_addr},

    # ── LAYER 2: Peel Chain (sequential) ────────────────────────────────
    {"key": "peel_hop_01",       "chain": "Ethereum", "label": "Peel Chain Hop 1",              "risk": 82, "addr_fn": _eth_addr},
    {"key": "peel_hop_02",       "chain": "Ethereum", "label": "Peel Chain Hop 2",              "risk": 78, "addr_fn": _eth_addr},
    {"key": "peel_hop_03",       "chain": "Ethereum", "label": "Peel Chain Hop 3",              "risk": 74, "addr_fn": _eth_addr},
    {"key": "peel_hop_04",       "chain": "Ethereum", "label": "Peel Chain Hop 4",              "risk": 70, "addr_fn": _eth_addr},
    {"key": "peel_vasp_01",      "chain": "Ethereum", "label": "Binance Deposit (peel 1)",      "risk": 76, "addr_fn": _eth_addr, "entity_name": "Binance",               "entity_type": EntityType.EXCHANGE,     "confidence": ConfidenceLevel.CONFIRMED},
    {"key": "peel_vasp_02",      "chain": "Ethereum", "label": "CoinDCX Deposit (peel 2)",      "risk": 72, "addr_fn": _eth_addr, "entity_name": "CoinDCX",               "entity_type": EntityType.EXCHANGE,     "confidence": ConfidenceLevel.CONFIRMED},
    {"key": "peel_vasp_03",      "chain": "Ethereum", "label": "WazirX Deposit (peel 3)",       "risk": 70, "addr_fn": _eth_addr, "entity_name": "WazirX",                "entity_type": EntityType.EXCHANGE,     "confidence": ConfidenceLevel.CONFIRMED},

    # ── LAYER 3: Cross-Chain Bridge ─────────────────────────────────────
    {"key": "bridge_eth",        "chain": "Ethereum", "label": "Bridge Lock Contract (ETH)",     "risk": 75, "addr_fn": _eth_addr, "entity_name": "Multichain Bridge",     "entity_type": EntityType.BRIDGE,       "confidence": ConfidenceLevel.HIGH_CONFIDENCE},
    {"key": "bridge_tron_recv",  "chain": "Tron",     "label": "Bridge Mint (TRON)",             "risk": 72, "addr_fn": _tron_addr},
    {"key": "tron_layering_01",  "chain": "Tron",     "label": "TRON Layering Wallet 1",         "risk": 70, "addr_fn": _tron_addr},
    {"key": "tron_layering_02",  "chain": "Tron",     "label": "TRON Layering Wallet 2",         "risk": 68, "addr_fn": _tron_addr},
    {"key": "tron_exit_vasp",    "chain": "Tron",     "label": "Huobi Deposit (TRON exit)",      "risk": 65, "addr_fn": _tron_addr, "entity_name": "Huobi",                "entity_type": EntityType.EXCHANGE,     "confidence": ConfidenceLevel.CONFIRMED},

    # ── LAYER 4: Mixer / Tumbler ────────────────────────────────────────
    {"key": "mixer_deposit",     "chain": "Ethereum", "label": "Tornado Cash Router",            "risk": 95, "addr_fn": _eth_addr, "entity_name": "Tornado Cash",          "entity_type": EntityType.MIXER,        "confidence": ConfidenceLevel.CONFIRMED},
    {"key": "mixer_out_01",      "chain": "Ethereum", "label": "Mixer Output 1 (clean)",         "risk": 88, "addr_fn": _eth_addr},
    {"key": "mixer_out_02",      "chain": "Ethereum", "label": "Mixer Output 2 (clean)",         "risk": 86, "addr_fn": _eth_addr},
    {"key": "mixer_out_03",      "chain": "Ethereum", "label": "Mixer Output 3 (clean)",         "risk": 84, "addr_fn": _eth_addr},
    {"key": "mixer_out_04",      "chain": "Ethereum", "label": "Mixer Output 4 (clean)",         "risk": 82, "addr_fn": _eth_addr},

    # ── LAYER 5: Cyclic Wash-Trade ──────────────────────────────────────
    {"key": "cycle_a",           "chain": "Ethereum", "label": "Wash-Trade Node A",              "risk": 78, "addr_fn": _eth_addr},
    {"key": "cycle_b",           "chain": "Ethereum", "label": "Wash-Trade Node B",              "risk": 76, "addr_fn": _eth_addr},
    {"key": "cycle_c",           "chain": "Ethereum", "label": "Wash-Trade Node C",              "risk": 74, "addr_fn": _eth_addr},
    {"key": "cycle_d",           "chain": "Ethereum", "label": "Wash-Trade Node D",              "risk": 72, "addr_fn": _eth_addr},
    {"key": "cycle_e",           "chain": "Ethereum", "label": "Wash-Trade Node E",              "risk": 70, "addr_fn": _eth_addr},

    # ── LAYER 6: Exchange Exit Ramp ─────────────────────────────────────
    {"key": "exit_kraken",       "chain": "Ethereum", "label": "Kraken Hot Wallet",              "risk": 80, "addr_fn": _eth_addr, "entity_name": "Kraken",                "entity_type": EntityType.EXCHANGE,     "confidence": ConfidenceLevel.CONFIRMED},
    {"key": "exit_kucoin",       "chain": "Ethereum", "label": "KuCoin Hot Wallet",              "risk": 78, "addr_fn": _eth_addr, "entity_name": "KuCoin",                "entity_type": EntityType.EXCHANGE,     "confidence": ConfidenceLevel.CONFIRMED},

    # ── LAYER 3b: Bitcoin Bridge ────────────────────────────────────────
    {"key": "bridge_btc_lock",   "chain": "Ethereum", "label": "RenBridge Lock (ETH→BTC)",       "risk": 72, "addr_fn": _eth_addr, "entity_name": "Ren Bridge",            "entity_type": EntityType.BRIDGE,       "confidence": ConfidenceLevel.HIGH_CONFIDENCE},
    {"key": "btc_recv",          "chain": "Bitcoin",  "label": "BTC Receiver",                   "risk": 68, "addr_fn": _btc_addr},
    {"key": "btc_hop",           "chain": "Bitcoin",  "label": "BTC Intermediate",               "risk": 65, "addr_fn": _btc_addr},
    {"key": "btc_exit_binance",  "chain": "Bitcoin",  "label": "Binance BTC Deposit",            "risk": 72, "addr_fn": _btc_addr, "entity_name": "Binance",               "entity_type": EntityType.EXCHANGE,     "confidence": ConfidenceLevel.CONFIRMED},
]
# fmt: on

# ---------------------------------------------------------------------------
# Transaction catalogue  (from_key, to_key, chain, value_usd, token, method,
#                          block, minutes_after_T0, note)
# ---------------------------------------------------------------------------
# fmt: off
TRANSACTIONS: list[dict] = [
    # ── L1: Smurfing (Source → 10 mules) ────────────────────────────────
    {"from": "victim_pool", "to": "smurf_01", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "transfer",         "block": 20_410_001, "dt": 0,   "note": "Smurfing split 1/10"},
    {"from": "victim_pool", "to": "smurf_02", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "transfer",         "block": 20_410_002, "dt": 3,   "note": "Smurfing split 2/10"},
    {"from": "victim_pool", "to": "smurf_03", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "transfer",         "block": 20_410_003, "dt": 5,   "note": "Smurfing split 3/10"},
    {"from": "victim_pool", "to": "smurf_04", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "transfer",         "block": 20_410_004, "dt": 8,   "note": "Smurfing split 4/10"},
    {"from": "victim_pool", "to": "smurf_05", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "transfer",         "block": 20_410_005, "dt": 10,  "note": "Smurfing split 5/10"},
    {"from": "victim_pool", "to": "smurf_06", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "transfer",         "block": 20_410_006, "dt": 13,  "note": "Smurfing split 6/10"},
    {"from": "victim_pool", "to": "smurf_07", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "transfer",         "block": 20_410_007, "dt": 16,  "note": "Smurfing split 7/10"},
    {"from": "victim_pool", "to": "smurf_08", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "transfer",         "block": 20_410_008, "dt": 19,  "note": "Smurfing split 8/10"},
    {"from": "victim_pool", "to": "smurf_09", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "transfer",         "block": 20_410_009, "dt": 22,  "note": "Smurfing split 9/10"},
    {"from": "victim_pool", "to": "smurf_10", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "transfer",         "block": 20_410_010, "dt": 25,  "note": "Smurfing split 10/10"},

    # ── L2: Peel Chain (Smurf 01→02→03→04 with VASP peels) ─────────────
    {"from": "smurf_01", "to": "peel_hop_01",  "chain": "Ethereum", "usd": 48000, "token": "ETH",  "method": "transfer",        "block": 20_410_050, "dt": 60,   "note": "Peel chain start"},
    {"from": "peel_hop_01", "to": "peel_vasp_01", "chain": "Ethereum", "usd": 12000, "token": "ETH", "method": "transfer",       "block": 20_410_051, "dt": 65,   "note": "Peel off to Binance"},
    {"from": "peel_hop_01", "to": "peel_hop_02",  "chain": "Ethereum", "usd": 36000, "token": "ETH", "method": "transfer",       "block": 20_410_055, "dt": 75,   "note": "Peel chain hop 2"},
    {"from": "peel_hop_02", "to": "peel_vasp_02", "chain": "Ethereum", "usd": 8000,  "token": "ETH", "method": "transfer",       "block": 20_410_060, "dt": 85,   "note": "Peel off to CoinDCX"},
    {"from": "peel_hop_02", "to": "peel_hop_03",  "chain": "Ethereum", "usd": 28000, "token": "ETH", "method": "transfer",       "block": 20_410_065, "dt": 95,   "note": "Peel chain hop 3"},
    {"from": "peel_hop_03", "to": "peel_vasp_03", "chain": "Ethereum", "usd": 5000,  "token": "ETH", "method": "transfer",       "block": 20_410_070, "dt": 105,  "note": "Peel off to WazirX"},
    {"from": "peel_hop_03", "to": "peel_hop_04",  "chain": "Ethereum", "usd": 23000, "token": "ETH", "method": "transfer",       "block": 20_410_075, "dt": 115,  "note": "Peel chain hop 4"},

    # ── L3a: Cross-Chain Bridge ETH → TRON ──────────────────────────────
    {"from": "smurf_02", "to": "bridge_eth",       "chain": "Ethereum", "usd": 50000, "token": "ETH",      "method": "lock",             "block": 20_410_100, "dt": 180,  "note": "Bridge lock deposit"},
    {"from": "bridge_eth", "to": "bridge_tron_recv","chain": "Tron",     "usd": 49800, "token": "USDT-TRC20","method": "mint",             "block": 68_200_001, "dt": 185,  "note": "Bridge mint on TRON"},
    {"from": "bridge_tron_recv", "to": "tron_layering_01", "chain": "Tron", "usd": 30000, "token": "USDT-TRC20", "method": "transfer",    "block": 68_200_050, "dt": 210,  "note": "TRON layering 1"},
    {"from": "bridge_tron_recv", "to": "tron_layering_02", "chain": "Tron", "usd": 19800, "token": "USDT-TRC20", "method": "transfer",    "block": 68_200_055, "dt": 215,  "note": "TRON layering 2"},
    {"from": "tron_layering_01", "to": "tron_exit_vasp",   "chain": "Tron", "usd": 30000, "token": "USDT-TRC20", "method": "transfer",    "block": 68_200_100, "dt": 360,  "note": "TRON exit to Huobi"},
    {"from": "tron_layering_02", "to": "tron_exit_vasp",   "chain": "Tron", "usd": 19800, "token": "USDT-TRC20", "method": "transfer",    "block": 68_200_110, "dt": 370,  "note": "TRON exit to Huobi (2)"},

    # ── L3b: Cross-Chain Bridge ETH → BTC ───────────────────────────────
    {"from": "smurf_03", "to": "bridge_btc_lock",  "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "lock",              "block": 20_410_200, "dt": 300,  "note": "RenBridge lock deposit"},
    {"from": "bridge_btc_lock", "to": "btc_recv",  "chain": "Bitcoin",  "usd": 49500, "token": "BTC",  "method": "mint",              "block": 860_001,    "dt": 310,  "note": "BTC mint via RenBridge"},
    {"from": "btc_recv", "to": "btc_hop",          "chain": "Bitcoin",  "usd": 49500, "token": "BTC",  "method": "transfer",          "block": 860_010,    "dt": 400,  "note": "BTC intermediate hop"},
    {"from": "btc_hop", "to": "btc_exit_binance",  "chain": "Bitcoin",  "usd": 49000, "token": "BTC",  "method": "transfer",          "block": 860_025,    "dt": 480,  "note": "BTC exit to Binance"},

    # ── L4: Mixer (Smurfs 04-06 → Tornado Cash → clean outputs) ────────
    {"from": "smurf_04", "to": "mixer_deposit", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "deposit",            "block": 20_410_300, "dt": 420,  "note": "Mixer deposit 1"},
    {"from": "smurf_05", "to": "mixer_deposit", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "deposit",            "block": 20_410_305, "dt": 425,  "note": "Mixer deposit 2"},
    {"from": "smurf_06", "to": "mixer_deposit", "chain": "Ethereum", "usd": 50000, "token": "ETH",  "method": "deposit",            "block": 20_410_310, "dt": 430,  "note": "Mixer deposit 3"},
    {"from": "mixer_deposit", "to": "mixer_out_01", "chain": "Ethereum", "usd": 37500, "token": "ETH", "method": "withdraw",         "block": 20_411_000, "dt": 1440, "note": "Mixer withdraw 1 (24h delay)"},
    {"from": "mixer_deposit", "to": "mixer_out_02", "chain": "Ethereum", "usd": 37500, "token": "ETH", "method": "withdraw",         "block": 20_411_005, "dt": 1445, "note": "Mixer withdraw 2"},
    {"from": "mixer_deposit", "to": "mixer_out_03", "chain": "Ethereum", "usd": 37500, "token": "ETH", "method": "withdraw",         "block": 20_411_010, "dt": 1450, "note": "Mixer withdraw 3"},
    {"from": "mixer_deposit", "to": "mixer_out_04", "chain": "Ethereum", "usd": 37500, "token": "ETH", "method": "withdraw",         "block": 20_411_015, "dt": 1455, "note": "Mixer withdraw 4"},

    # ── L5: Cyclic Wash-Trade (5-node ring from remaining smurfs) ───────
    {"from": "smurf_07", "to": "cycle_a",   "chain": "Ethereum", "usd": 50000, "token": "ETH", "method": "transfer", "block": 20_410_400, "dt": 600,  "note": "Wash-trade entry"},
    {"from": "cycle_a",  "to": "cycle_b",   "chain": "Ethereum", "usd": 48000, "token": "ETH", "method": "transfer", "block": 20_410_410, "dt": 610,  "note": "Wash-trade ring A→B"},
    {"from": "cycle_b",  "to": "cycle_c",   "chain": "Ethereum", "usd": 46000, "token": "ETH", "method": "transfer", "block": 20_410_420, "dt": 620,  "note": "Wash-trade ring B→C"},
    {"from": "cycle_c",  "to": "cycle_d",   "chain": "Ethereum", "usd": 44000, "token": "ETH", "method": "transfer", "block": 20_410_430, "dt": 630,  "note": "Wash-trade ring C→D"},
    {"from": "cycle_d",  "to": "cycle_e",   "chain": "Ethereum", "usd": 42000, "token": "ETH", "method": "transfer", "block": 20_410_440, "dt": 640,  "note": "Wash-trade ring D→E"},
    {"from": "cycle_e",  "to": "cycle_a",   "chain": "Ethereum", "usd": 40000, "token": "ETH", "method": "transfer", "block": 20_410_450, "dt": 650,  "note": "Wash-trade ring E→A (cycle complete!)"},

    # ── L6: Exchange Exit Ramp (mixer outputs → exchanges) ──────────────
    {"from": "mixer_out_01", "to": "exit_kraken", "chain": "Ethereum", "usd": 37500, "token": "ETH", "method": "transfer", "block": 20_412_000, "dt": 2880, "note": "Exit to Kraken"},
    {"from": "mixer_out_02", "to": "exit_kucoin", "chain": "Ethereum", "usd": 37500, "token": "ETH", "method": "transfer", "block": 20_412_005, "dt": 2885, "note": "Exit to KuCoin"},
    {"from": "mixer_out_03", "to": "exit_kraken", "chain": "Ethereum", "usd": 37500, "token": "ETH", "method": "transfer", "block": 20_412_010, "dt": 2890, "note": "Exit to Kraken (2)"},
    {"from": "mixer_out_04", "to": "exit_kucoin", "chain": "Ethereum", "usd": 37500, "token": "ETH", "method": "transfer", "block": 20_412_015, "dt": 2895, "note": "Exit to KuCoin (2)"},

    # ── L6b: Remaining smurfs direct exit ───────────────────────────────
    {"from": "smurf_08",  "to": "exit_kraken", "chain": "Ethereum", "usd": 50000, "token": "ETH", "method": "transfer", "block": 20_412_100, "dt": 3000, "note": "Direct smurf exit to Kraken"},
    {"from": "smurf_09",  "to": "exit_kucoin", "chain": "Ethereum", "usd": 50000, "token": "ETH", "method": "transfer", "block": 20_412_105, "dt": 3005, "note": "Direct smurf exit to KuCoin"},
    {"from": "smurf_10",  "to": "peel_vasp_01","chain": "Ethereum", "usd": 50000, "token": "ETH", "method": "transfer", "block": 20_412_110, "dt": 3010, "note": "Direct smurf exit to Binance"},

    # ── Peel chain remainder → Kraken ───────────────────────────────────
    {"from": "peel_hop_04", "to": "exit_kraken","chain": "Ethereum", "usd": 23000, "token": "ETH", "method": "transfer", "block": 20_412_200, "dt": 3060, "note": "Peel chain tail to Kraken"},

    # ── Wash-trade exit (cycle_a drains to exchange) ────────────────────
    {"from": "cycle_a", "to": "exit_kucoin",   "chain": "Ethereum", "usd": 40000, "token": "ETH", "method": "transfer", "block": 20_412_300, "dt": 3120, "note": "Wash-trade cycle exit to KuCoin"},
]
# fmt: on


# ============================================================
# Seed logic
# ============================================================


async def _clear_existing() -> None:
    """Delete any previously seeded complex-fraud data."""
    await Neo4jClient.initialize()
    async with Neo4jClient.session() as session:
        await session.run(
            "MATCH (n) WHERE n.metadata IS NOT NULL AND n.metadata CONTAINS $marker "
            "DETACH DELETE n",
            marker=SYNTHETIC_MARKER,
        )
    print("  ↳ Cleared existing complex-fraud demo data")


async def _seed_wallets() -> dict[str, dict]:
    """Create all Wallet nodes and return a key→info lookup."""
    lookup: dict[str, dict] = {}
    for w in WALLETS:
        addr = w["addr_fn"](w["key"])
        wallet = GraphWallet(
            address=addr,
            chain=w["chain"],
            label=w["label"],
            risk_score=float(w["risk"]),
            first_seen=T0,
            last_seen=T0 + timedelta(hours=72),
            total_sent=0,
            total_received=0,
            tx_count=0,
            entity_name=w.get("entity_name"),
            entity_type=w.get("entity_type"),
            entity_confidence=w.get("confidence", ConfidenceLevel.UNKNOWN),
            metadata={"source": SYNTHETIC_MARKER, "role": "actor", "label": w["label"]},
        )
        await graph_repository.upsert_wallet(wallet)
        lookup[w["key"]] = {
            "address": addr,
            "chain": w["chain"],
            "entity_name": w.get("entity_name"),
            "entity_type": w.get("entity_type"),
            "confidence": w.get("confidence"),
        }
    print(f"  ↳ Created {len(lookup)} wallet nodes")
    return lookup


async def _seed_transactions(lookup: dict[str, dict]) -> int:
    """Create all Transaction nodes and link them to wallets."""
    count = 0
    for tx_def in TRANSACTIONS:
        from_info = lookup[tx_def["from"]]
        to_info = lookup[tx_def["to"]]
        chain = tx_def["chain"]
        timestamp = T0 + timedelta(minutes=tx_def["dt"])
        h = _tx_hash(f"{tx_def['from']}->{tx_def['to']}-{tx_def['dt']}")

        tx = GraphTransaction(
            tx_hash=h,
            chain=chain,
            block_number=tx_def["block"],
            timestamp=timestamp,
            from_address=from_info["address"],
            to_address=to_info["address"],
            value=str(tx_def["usd"]),
            value_usd=float(tx_def["usd"]),
            token_address=None,
            token_symbol=tx_def["token"],
            method=tx_def["method"],
            gas_used=21000 if tx_def["method"] == "transfer" else 65000,
            gas_price="20000000000",
            is_suspicious=True,
            metadata={
                "source": SYNTHETIC_MARKER,
                "note": tx_def["note"],
                "layer": tx_def["note"].split()[0] if tx_def["note"] else "",
            },
        )
        await graph_repository.upsert_transaction(tx)
        await graph_repository.link_wallet_transaction(from_info["address"], chain, h, "sent")
        await graph_repository.link_wallet_transaction(to_info["address"], chain, h, "received")
        count += 1
    print(f"  ↳ Created {count} transaction nodes with SENT/RECEIVED links")
    return count


async def _seed_entities(lookup: dict[str, dict]) -> int:
    """Create Entity nodes for attributed wallets and link them."""
    count = 0
    for w in WALLETS:
        if not w.get("entity_name"):
            continue
        info = lookup[w["key"]]
        entity = GraphEntity(
            name=w["entity_name"],
            entity_type=w.get("entity_type", EntityType.UNKNOWN),
            address=info["address"],
            chain=info["chain"],
            confidence=w.get("confidence", ConfidenceLevel.UNKNOWN),
            source=SYNTHETIC_MARKER,
            tags=[w["entity_type"].value] if w.get("entity_type") else [],
            metadata={"source": SYNTHETIC_MARKER},
            first_seen=T0,
            last_verified=T0 + timedelta(hours=72),
        )
        await graph_repository.upsert_entity(entity)
        await graph_repository.link_wallet_entity(info["address"], info["chain"], info["address"])
        count += 1
    print(f"  ↳ Created {count} entity nodes with BELONGS_TO links")
    return count


async def _seed_postgres(lookup: dict[str, dict]) -> None:
    """Seed PostgreSQL with the same case, wallets, transactions, run, and report."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    case_number = "TRX-20240116-0050"

    async with async_session() as session:
        # Delete existing case if present (cascades to wallets, txs, runs, reports)
        await session.execute(delete(Case).where(Case.case_number == case_number))
        await session.flush()

        # Find demo analyst user to assign
        res = await session.execute(select(User).where(User.email == "analyst.a@tracex.gov"))
        owner = res.scalar_one_or_none()
        if not owner:
            res_any = await session.execute(select(User).limit(1))
            owner = res_any.scalar_one_or_none()
        owner_id = owner.id if owner else None

        total_flow = sum(t["usd"] for t in TRANSACTIONS)
        case_id = UUID("1433b779-a4ef-43ad-b6b9-b5213c7e91a8")
        case = Case(
            id=case_id,
            case_number=case_number,
            title="Multi-Layered Fraud Syndicate - 6-Pattern Laundering",
            crime_type=CrimeType.MONEY_LAUNDERING,
            description=(
                "A multi-layered task-scam syndicate moving $1.99M across Ethereum, TRON, and Bitcoin "
                "demonstrating all six laundering motifs: smurfing fan-out across 10 mules, a 4-hop peel chain, "
                "cross-chain bridge hops to TRON and Bitcoin, Tornado Cash mixer cycle, 5-node cyclic wash-trade, "
                "and exchange off-ramps."
            ),
            status=CaseStatus.IN_PROGRESS,
            assigned_to=owner_id,
            case_metadata={
                "source": SYNTHETIC_MARKER,
                "opened_at": T0.isoformat(),
                "chains": ["Ethereum", "Tron", "Bitcoin"],
                "tags": [
                    "Smurfing",
                    "Peel Chain",
                    "Cross-chain Bridge",
                    "Tornado Cash",
                    "Cyclic Wash-Trade",
                    "Exchange Off-ramp",
                ],
                "aggregate_flow_usd": total_flow,
                "primary_wallet": lookup["victim_pool"]["address"],
            },
            created_at=T0,
            updated_at=T0 + timedelta(hours=72),
        )
        session.add(case)
        await session.flush()

        # Wallets
        wallet_rows: dict[str, Wallet] = {}
        first_tx_hashes: dict[str, str] = {}
        for tx_def in TRANSACTIONS:
            h = _tx_hash(f"{tx_def['from']}->{tx_def['to']}-{tx_def['dt']}")
            first_tx_hashes.setdefault(tx_def["from"], h)
            first_tx_hashes.setdefault(tx_def["to"], h)

        for w in WALLETS:
            info = lookup[w["key"]]
            addr = info["address"]
            chain = w["chain"]
            has_entity = bool(w.get("entity_name"))
            w_row = Wallet(
                id=uuid4(),
                case_id=case_id,
                address=addr,
                chain=chain,
                label=w["label"][:100],
                attribution_status=AttributionStatus.CONFIRMED
                if has_entity
                else AttributionStatus.UNVERIFIED,
                risk_score=float(w["risk"]),
                entity_name=w.get("entity_name"),
                entity_type=w["entity_type"].value if w.get("entity_type") else None,
                entity_confidence=w["confidence"].value if w.get("confidence") else None,
                first_seen_tx_hash=first_tx_hashes.get(w["key"]),
                wallet_metadata={
                    "source": SYNTHETIC_MARKER,
                    "key": w["key"],
                    "chain": chain,
                },
                created_at=T0,
                updated_at=T0 + timedelta(hours=72),
            )
            session.add(w_row)
            wallet_rows[w["key"]] = w_row
        await session.flush()

        # Transactions
        for tx_def in TRANSACTIONS:
            h = _tx_hash(f"{tx_def['from']}->{tx_def['to']}-{tx_def['dt']}")
            from_info = lookup[tx_def["from"]]
            to_info = lookup[tx_def["to"]]
            tx_time = T0 + timedelta(minutes=tx_def["dt"])
            session.add(
                Transaction(
                    id=uuid4(),
                    wallet_id=wallet_rows[tx_def["from"]].id,
                    tx_hash=h,
                    block_number=tx_def["block"],
                    timestamp=tx_time,
                    from_address=from_info["address"],
                    to_address=to_info["address"],
                    value=str(tx_def["usd"]),
                    value_usd=float(tx_def["usd"]),
                    token_address=None,
                    token_symbol=tx_def["token"],
                    method=tx_def["method"],
                    is_suspicious=True,
                    transaction_metadata={
                        "source": SYNTHETIC_MARKER,
                        "note": tx_def["note"],
                    },
                    created_at=tx_time,
                    updated_at=tx_time,
                )
            )
        await session.flush()

        # Investigation Run
        victim_wallet_row = wallet_rows["victim_pool"]
        session.add(
            InvestigationRun(
                id=uuid4(),
                case_id=case_id,
                wallet_id=victim_wallet_row.id,
                status=InvestigationStatus.COMPLETED,
                started_at=T0 + timedelta(minutes=30),
                completed_at=T0 + timedelta(hours=1),
                config={
                    "trace_depth": 6,
                    "max_transactions": 100,
                    "chains": ["Ethereum", "Tron", "Bitcoin"],
                    "include_exchange_sweeps": True,
                    "demo": True,
                },
                result_summary={
                    "transactions_found": len(TRANSACTIONS),
                    "suspicious_transactions": len(TRANSACTIONS),
                    "unique_addresses": len(WALLETS),
                    "aggregate_flow_usd": total_flow,
                    "largest_transaction_usd": max(t["usd"] for t in TRANSACTIONS),
                    "mixer_transactions": 7,
                    "chains_analyzed": ["Bitcoin", "Ethereum", "Tron"],
                    "vasp_endpoints": ["Binance", "CoinDCX", "Huobi", "Kraken", "KuCoin", "WazirX"],
                    "laundering_motifs_detected": [
                        "Smurfing (Fan-Out into 10 Mules)",
                        "Peel Chain (4-hop corridor with VASP cash-outs)",
                        "Cross-Chain Bridge Hops (ETH->TRON, ETH->BTC)",
                        "Mixer Cycle (Tornado Cash 24h delay)",
                        "Cyclic Wash-Trade (5-Node Loop)",
                        "Exchange Exit Ramps (6 VASPs)",
                    ],
                    "demo": True,
                },
                created_at=T0 + timedelta(minutes=30),
                updated_at=T0 + timedelta(hours=1),
            )
        )

        # Report
        if owner_id:
            session.add(
                Report(
                    id=uuid4(),
                    case_id=case_id,
                    title="Multi-Layered Fraud Syndicate - Forensic Investigation Report",
                    summary=(
                        f"{len(TRANSACTIONS)} transactions across 3 chains (Ethereum, Tron, Bitcoin) "
                        f"and {len(WALLETS)} wallets, USD {total_flow:,.0f} aggregate flow. "
                        "All 6 laundering motifs detected: Smurfing, Peel Chain, Cross-Chain Bridges, "
                        "Mixer, Cyclic Wash-Trading, and Exchange Off-Ramping."
                    ),
                    findings={
                        "executive_summary": (
                            "Synthetic 72-hour demonstration of a task-scam syndicate laundering funds through "
                            "six distinct obfuscation patterns across Ethereum, Tron, and Bitcoin."
                        ),
                        "key_findings": [
                            "10-mule fan-out smurfing sub-threshold transfers ($50,000 each)",
                            "Peel chain peeling off funds to Binance, CoinDCX, and WazirX",
                            "Cross-chain bridging to TRON (USDT-TRC20) and Bitcoin (RenBridge)",
                            "Mixer laundering cycle through Tornado Cash with 24-hour delayed withdrawals",
                            "5-node wash-trading cyclic loop returning funds to origin",
                            "Final off-ramping into Kraken, KuCoin, and Huobi exchange hot wallets",
                        ],
                        "vasp_endpoints": [
                            "Binance",
                            "Kraken",
                            "KuCoin",
                            "Huobi",
                            "CoinDCX",
                            "WazirX",
                        ],
                    },
                    risk_assessment={
                        "overall_risk": "CRITICAL",
                        "highest_score": 98.0,
                        "average_score": 57.5,
                        "critical_wallets": 3,
                        "mixer_exposure": True,
                        "motifs_detected": 6,
                    },
                    generated_by=owner_id,
                    format="pdf",
                    created_at=T0 + timedelta(hours=72),
                    updated_at=T0 + timedelta(hours=72),
                )
            )

        await session.commit()
    await engine.dispose()
    print(
        f"  ↳ Seeded PostgreSQL case {case_number} with {len(WALLETS)} wallets, {len(TRANSACTIONS)} txs"
    )


async def main() -> None:
    print("=" * 60)
    print("TRACE-X Complex Fraud Demo Seeder")
    print("=" * 60)

    await _clear_existing()
    lookup = await _seed_wallets()
    tx_count = await _seed_transactions(lookup)
    entity_count = await _seed_entities(lookup)
    await _seed_postgres(lookup)

    total_usd = sum(t["usd"] for t in TRANSACTIONS)
    chains = sorted({t["chain"] for t in TRANSACTIONS})

    print("=" * 60)
    print("✅ Seeding complete!")
    print(f"   Wallets:      {len(lookup)}")
    print(f"   Transactions: {tx_count}")
    print(f"   Entities:     {entity_count}")
    print(f"   Total Flow:   ${total_usd:,.0f}")
    print(f"   Chains:       {', '.join(chains)}")
    print("   Patterns:     Smurfing, Peel Chain, Bridge Hop (ETH→TRON, ETH→BTC),")
    print("                 Mixer (Tornado Cash), Cyclic Wash-Trade, Exchange Exit")
    print("=" * 60)

    await Neo4jClient.close()


if __name__ == "__main__":
    asyncio.run(main())
