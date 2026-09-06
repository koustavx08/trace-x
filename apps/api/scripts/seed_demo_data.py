#!/usr/bin/env python3
"""
TRACE-X Demo Data Seeder
Generates synthetic SIH 2026 investigation cases for demonstration purposes.
All data is explicitly marked as SYNTHETIC.
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Add apps/api (this script's parent's parent) to the path so `src` imports
# resolve regardless of the caller's cwd.
API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

from src.auth import hash_password
from src.core.config import get_settings
from src.core.database import Base
from src.graph.client import Neo4jClient
from src.graph.models import ConfidenceLevel, EntityType, GraphEntity, GraphTransaction, GraphWallet
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
    UserRole,
    Wallet,
)

settings = get_settings()

SYNTHETIC_MARKER = "SYNTHETIC_DEMO_DATA"

# ============================================================
# SYNTHETIC CASES - SIH 2026 Demo Scenarios
# ============================================================

DEMO_CASES = [
    {
        "case_number": "TRX-20240115-0042",
        "title": "DeFi Protocol Flash Loan Exploit - Protocol X",
        "crime_type": CrimeType.FRAUD,
        "description": (
            "Major DeFi protocol exploit involving flash loan attack across multiple protocols. "
            "Initial attack vector identified as a vulnerable oracle price feed on Protocol X. "
            "Attacker borrowed 50,000 ETH via flash loan, manipulated oracle prices on DEX Y, "
            "drained liquidity pools, then repaid loan. Funds traced through Tornado Cash "
            "and multiple DEX swaps across Ethereum and Polygon. "
            "[SYNTHETIC DEMO DATA - Not real investigation]"
        ),
        "status": CaseStatus.IN_PROGRESS,
        "wallets": [
            {
                "address": "0x742D35CC6634c0532925A3b844BC9E7595F0BEb0",
                "chain": "Ethereum",
                "label": "Attacker - Flash Loan Originator",
                "attribution_status": AttributionStatus.ATTRIBUTED,
                "risk_score": 95.0,
                "entity_name": "Unknown Attacker",
                "entity_confidence": "PROBABLE",
            },
            {
                "address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
                "chain": "Ethereum",
                "label": "Uniswap V3 Router - First Hop",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 45.0,
                "entity_name": "Uniswap V3",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "chain": "Ethereum",
                "label": "Uniswap V2 Router - Intermediate",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 42.0,
                "entity_name": "Uniswap V2",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0x722122dF12D4e14e13Ac3b6895a86e84145b6967",
                "chain": "Ethereum",
                "label": "Tornado Cash - Mixer Deposit",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 98.0,
                "entity_name": "Tornado Cash",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0xA0b86a33e6441b8C4C8c8C8c8c8c8c8c8c8C8c8C",
                "chain": "Polygon",
                "label": "Polygon Bridge - Cross-chain Transfer",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 55.0,
                "entity_name": "Polygon Bridge",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "chain": "Ethereum",
                "label": "Binance Deposit - Final Destination",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 88.0,
                "entity_name": "Binance",
                "entity_confidence": "CONFIRMED",
            },
        ],
        "transactions": [
            {
                "from_idx": 0,
                "to_idx": 1,
                "value_eth": 50000,
                "method": "flash_loan",
                "suspicious": True,
            },
            {"from_idx": 1, "to_idx": 2, "value_eth": 49800, "method": "swap", "suspicious": True},
            {
                "from_idx": 2,
                "to_idx": 3,
                "value_eth": 49500,
                "method": "deposit",
                "suspicious": True,
            },
            {
                "from_idx": 3,
                "to_idx": 4,
                "value_eth": 49000,
                "method": "bridge",
                "suspicious": True,
            },
            {
                "from_idx": 4,
                "to_idx": 5,
                "value_eth": 48500,
                "method": "deposit",
                "suspicious": True,
            },
        ],
    },
    {
        "case_number": "TRX-20240114-0038",
        "title": "Ransomware Payment Tracing - LockBit 3.0 Affiliate",
        "crime_type": CrimeType.RANSOMWARE,
        "description": (
            "Tracing ransomware payments from LockBit 3.0 affiliate across multiple chains. "
            "Victim organization paid 25 BTC equivalent in ETH/USDT. Payments split across "
            "multiple wallets, traced through Wasabi Wallet coinjoins, then to nested "
            "exchange deposits. Cross-chain movement via Polygon and Arbitrum bridges. "
            "[SYNTHETIC DEMO DATA - Not real investigation]"
        ),
        "status": CaseStatus.OPEN,
        "wallets": [
            {
                "address": "0x8aD1e08C7793af67e9d92fe308d5697FB81d3E43",
                "chain": "Ethereum",
                "label": "Ransom Payment - Initial Wallet",
                "attribution_status": AttributionStatus.UNDER_REVIEW,
                "risk_score": 92.0,
                "entity_name": "LockBit Affiliate Wallet",
                "entity_confidence": "HIGH_CONFIDENCE",
            },
            {
                "address": "0x503828976D22510aad0201ac7EC88293211D23Da",
                "chain": "Ethereum",
                "label": "CoinJoin - Wasabi Wallet",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 85.0,
                "entity_name": "Wasabi Wallet",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",
                "chain": "Ethereum",
                "label": "Kraken Deposit - Exchange Off-ramp",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 78.0,
                "entity_name": "Kraken",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0x0A869d79a7052c7f1b55a8EBabAa43105310D4D2",
                "chain": "Ethereum",
                "label": "Kraken Deposit - Secondary",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 75.0,
                "entity_name": "Kraken",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0x831517E7E53A5A6cC7A8A8A8A8A8A8A8A8A8A8A8",
                "chain": "Arbitrum",
                "label": "Arbitrum Bridge - Layer 2 Movement",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 60.0,
                "entity_name": "Arbitrum Bridge",
                "entity_confidence": "HIGH_CONFIDENCE",
            },
        ],
        "transactions": [
            {
                "from_idx": 0,
                "to_idx": 1,
                "value_eth": 850,
                "method": "coinjoin",
                "suspicious": True,
            },
            {"from_idx": 1, "to_idx": 2, "value_eth": 420, "method": "deposit", "suspicious": True},
            {"from_idx": 1, "to_idx": 3, "value_eth": 430, "method": "deposit", "suspicious": True},
            {"from_idx": 0, "to_idx": 4, "value_eth": 100, "method": "bridge", "suspicious": False},
        ],
    },
    {
        "case_number": "TRX-20240113-0029",
        "title": "International Money Laundering Ring - Nested Exchanges",
        "crime_type": CrimeType.MONEY_LAUNDERING,
        "description": (
            "International money laundering operation using nested exchange structure. "
            "Funds from predicate offenses (fraud, drug trafficking) moved through "
            "layered exchange deposits, DEX swaps, and cross-chain bridges. "
            "Network of 40+ wallets identified. Peel chain pattern with round amounts. "
            "Final off-ramps at Huobi, OKX, and Gate.io. "
            "[SYNTHETIC DEMO DATA - Not real investigation]"
        ),
        "status": CaseStatus.CLOSED,
        "wallets": [
            {
                "address": "0x0000000000000000000000000000000000001010",
                "chain": "Ethereum",
                "label": "Huobi Hot Wallet - Primary Off-ramp",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 82.0,
                "entity_name": "Huobi",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0x0000000000000000000000000000000000001011",
                "chain": "Ethereum",
                "label": "OKX Deposit Wallet",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 80.0,
                "entity_name": "OKX",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0x0000000000000000000000000000000000001012",
                "chain": "Ethereum",
                "label": "Gate.io Deposit Wallet",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 78.0,
                "entity_name": "Gate.io",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
                "chain": "Ethereum",
                "label": "DAI Stablecoin - Intermediate",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 12.0,
                "entity_name": "DAI Stablecoin",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "chain": "Ethereum",
                "label": "WETH - Wrapped Ether Contract",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 10.0,
                "entity_name": "WETH",
                "entity_confidence": "CONFIRMED",
            },
        ],
        "transactions": [
            {"from_idx": 3, "to_idx": 4, "value_eth": 10000, "method": "wrap", "suspicious": False},
            {
                "from_idx": 4,
                "to_idx": 0,
                "value_eth": 5000,
                "method": "deposit",
                "suspicious": True,
            },
            {
                "from_idx": 4,
                "to_idx": 1,
                "value_eth": 3000,
                "method": "deposit",
                "suspicious": True,
            },
            {
                "from_idx": 4,
                "to_idx": 2,
                "value_eth": 2000,
                "method": "deposit",
                "suspicious": True,
            },
        ],
    },
    {
        "case_number": "TRX-20240112-0017",
        "title": "Darknet Market Seizure - Hydra Market Successor",
        "crime_type": CrimeType.DARKNET_MARKET,
        "description": (
            "Cryptocurrency seizure from darknet marketplace successor to Hydra. "
            "Marketplace operated on Tor with Bitcoin and Monero primary, "
            "but used Ethereum/Polygon for vendor bond escrow. "
            "Seized 150+ vendor wallets, 500+ buyer wallets. "
            "Funds traced to multiple nested exchange deposits. "
            "[SYNTHETIC DEMO DATA - Not real investigation]"
        ),
        "status": CaseStatus.ARCHIVED,
        "wallets": [
            {
                "address": "0x159939f79D0B3D4e752912fA658A4D3776c9b5e3",
                "chain": "Ethereum",
                "label": "Bybit Deposit - Vendor Proceeds",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 75.0,
                "entity_name": "Bybit",
                "entity_confidence": "HIGH_CONFIDENCE",
            },
            {
                "address": "0x0000000000000000000000000000000000001010",
                "chain": "Polygon",
                "label": "Polygon Bridge - Cross-chain Escrow",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 65.0,
                "entity_name": "Polygon Bridge",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0xA0b86a33e6441b8C4C8c8C8c8c8c8c8c8c8C8c8C",
                "chain": "Polygon",
                "label": "USDC on Polygon - Stablecoin Escrow",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 25.0,
                "entity_name": "USDC (Polygon)",
                "entity_confidence": "CONFIRMED",
            },
        ],
        "transactions": [
            {"from_idx": 0, "to_idx": 1, "value_eth": 250, "method": "bridge", "suspicious": True},
            {
                "from_idx": 1,
                "to_idx": 2,
                "value_eth": 245,
                "method": "transfer",
                "suspicious": False,
            },
        ],
    },
    {
        "case_number": "TRX-20240111-0009",
        "title": "Sanctions Evasion - Russian Oligarch Crypto Holdings",
        "crime_type": CrimeType.SANCTIONS_EVASION,
        "description": (
            "Tracking sanctions evasion through crypto mixers and DeFi protocols. "
            "OFAC SDN-listed individual using Tornado Cash, Railgun, and cross-chain "
            "bridges to obscure ownership of ~$50M in crypto assets. "
            "Nested transactions through multiple DeFi protocols before "
            "final conversion to stablecoins on centralized exchanges. "
            "[SYNTHETIC DEMO DATA - Not real investigation]"
        ),
        "status": CaseStatus.IN_PROGRESS,
        "wallets": [
            {
                "address": "0x169455c72558a2D9A2C4a5b8F6e9e8D7a6B5c4D3",
                "chain": "Ethereum",
                "label": "Tornado Cash - Secondary Contract",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 99.0,
                "entity_name": "Tornado Cash",
                "entity_confidence": "CONFIRMED",
            },
            {
                "address": "0x0000000000000000000000000000000000001013",
                "chain": "Ethereum",
                "label": "Railgun - Privacy Protocol",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 95.0,
                "entity_name": "Railgun",
                "entity_confidence": "HIGH_CONFIDENCE",
            },
            {
                "address": "0x0000000000000000000000000000000000001014",
                "chain": "BSC",
                "label": "Binance Smart Chain - Bridge Destination",
                "attribution_status": AttributionStatus.ATTRIBUTED,
                "risk_score": 85.0,
                "entity_name": "BSC Bridge",
                "entity_confidence": "PROBABLE",
            },
            {
                "address": "0x0000000000000000000000000000000000001015",
                "chain": "Ethereum",
                "label": "Binance - Final Off-ramp",
                "attribution_status": AttributionStatus.CONFIRMED,
                "risk_score": 90.0,
                "entity_name": "Binance",
                "entity_confidence": "CONFIRMED",
            },
        ],
        "transactions": [
            {
                "from_idx": 0,
                "to_idx": 1,
                "value_eth": 5000,
                "method": "privacy_transfer",
                "suspicious": True,
            },
            {"from_idx": 1, "to_idx": 2, "value_eth": 4900, "method": "bridge", "suspicious": True},
            {
                "from_idx": 2,
                "to_idx": 3,
                "value_eth": 4800,
                "method": "deposit",
                "suspicious": True,
            },
        ],
    },
]

# ============================================================
# ENTITY INTELLIGENCE - Pre-loaded Known Entities
# ============================================================

DEMO_ENTITIES = [
    # Major Exchanges (CONFIRMED)
    {
        "name": "Binance",
        "entity_type": EntityType.EXCHANGE,
        "address": "0x28C6c06298d514Db089934071355E5743bf21d60",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    {
        "name": "Binance",
        "entity_type": EntityType.EXCHANGE,
        "address": "0x21a31Ee1afC51d94C2eF3CAaDB94D5c86C1F9e3d",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    {
        "name": "Binance",
        "entity_type": EntityType.EXCHANGE,
        "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    {
        "name": "Coinbase",
        "entity_type": EntityType.EXCHANGE,
        "address": "0xA9d1e08C7793af67e9d92fe308d5697FB81d3E43",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    {
        "name": "Coinbase",
        "entity_type": EntityType.EXCHANGE,
        "address": "0x503828976D22510aad0201ac7EC88293211D23Da",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    {
        "name": "Kraken",
        "entity_type": EntityType.EXCHANGE,
        "address": "0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    {
        "name": "Kraken",
        "entity_type": EntityType.EXCHANGE,
        "address": "0x0A869d79a7052c7f1b55a8EBabAa43105310D4D2",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    {
        "name": "OKX",
        "entity_type": EntityType.EXCHANGE,
        "address": "0x8A96747c82B41E8B7A0000000000000000000000",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    {
        "name": "Bybit",
        "entity_type": EntityType.EXCHANGE,
        "address": "0x159939f79D0B3D4e752912fA658A4D3776c9b5e3",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    {
        "name": "Huobi",
        "entity_type": EntityType.EXCHANGE,
        "address": "0x0000000000000000000000000000000000001010",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    {
        "name": "KuCoin",
        "entity_type": EntityType.EXCHANGE,
        "address": "0x0000000000000000000000000000000000001011",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    {
        "name": "Gate.io",
        "entity_type": EntityType.EXCHANGE,
        "address": "0x0000000000000000000000000000000000001012",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.PROBABLE,
        "source": "exchange_directory",
        "tags": ["cex", "kyc"],
    },
    # Mixers (CONFIRMED/HIGH)
    {
        "name": "Tornado Cash",
        "entity_type": EntityType.MIXER,
        "address": "0x722122dF12D4e14e13Ac3b6895a86e84145b6967",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "mixer_directory",
        "tags": ["mixer", "privacy", "high_risk"],
    },
    {
        "name": "Tornado Cash",
        "entity_type": EntityType.MIXER,
        "address": "0x169455c72558a2D9A2C4a5b8F6e9e8D7a6B5c4D3",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "mixer_directory",
        "tags": ["mixer", "privacy", "high_risk"],
    },
    {
        "name": "Wasabi Wallet",
        "entity_type": EntityType.MIXER,
        "address": "0x0000000000000000000000000000000000001010",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.PROBABLE,
        "source": "mixer_directory",
        "tags": ["mixer", "coinjoin", "privacy"],
    },
    {
        "name": "Railgun",
        "entity_type": EntityType.MIXER,
        "address": "0x0000000000000000000000000000000000001013",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
        "source": "mixer_directory",
        "tags": ["mixer", "privacy", "zk"],
    },
    # Bridges (CONFIRMED/HIGH)
    {
        "name": "Polygon Bridge",
        "entity_type": EntityType.BRIDGE,
        "address": "0xA0c68C638235ee32657e8f720a23ceC1bFc77C77",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "bridge_directory",
        "tags": ["bridge", "cross_chain"],
    },
    {
        "name": "Polygon Bridge",
        "entity_type": EntityType.BRIDGE,
        "address": "0x0000000000000000000000000000000000001010",
        "chain": "Polygon",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "bridge_directory",
        "tags": ["bridge", "cross_chain"],
    },
    {
        "name": "Arbitrum Bridge",
        "entity_type": EntityType.BRIDGE,
        "address": "0x831517E7E53A5A6cC7A8A8A8A8A8A8A8A8A8A8A8",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
        "source": "bridge_directory",
        "tags": ["bridge", "l2"],
    },
    {
        "name": "Optimism Bridge",
        "entity_type": EntityType.BRIDGE,
        "address": "0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
        "source": "bridge_directory",
        "tags": ["bridge", "l2"],
    },
    {
        "name": "BSC Bridge",
        "entity_type": EntityType.BRIDGE,
        "address": "0x0000000000000000000000000000000000001014",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.PROBABLE,
        "source": "bridge_directory",
        "tags": ["bridge", "cross_chain"],
    },
    # DeFi Protocols
    {
        "name": "Uniswap V3",
        "entity_type": EntityType.DEFI,
        "address": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "defi_directory",
        "tags": ["defi", "dex"],
    },
    {
        "name": "Uniswap V2",
        "entity_type": EntityType.DEFI,
        "address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "defi_directory",
        "tags": ["defi", "dex"],
    },
    {
        "name": "Aave V3",
        "entity_type": EntityType.DEFI,
        "address": "0x87870B93F8aD8E5F8a8A8A8A8A8A8A8A8A8A8A8A",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.HIGH_CONFIDENCE,
        "source": "defi_directory",
        "tags": ["defi", "lending"],
    },
    # Stablecoins/Tokens
    {
        "name": "USDC (Ethereum)",
        "entity_type": EntityType.DEFI,
        "address": "0xA0b86a33e6441b8C4C8c8C8c8c8c8c8c8c8C8c8C",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "token_registry",
        "tags": ["stablecoin", "usdc"],
    },
    {
        "name": "USDC (Polygon)",
        "entity_type": EntityType.DEFI,
        "address": "0xA0b86a33e6441b8C4C8c8C8c8c8c8c8c8c8C8c8C",
        "chain": "Polygon",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "token_registry",
        "tags": ["stablecoin", "usdc"],
    },
    {
        "name": "DAI Stablecoin",
        "entity_type": EntityType.DEFI,
        "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "token_registry",
        "tags": ["stablecoin", "dai"],
    },
    {
        "name": "WETH",
        "entity_type": EntityType.DEFI,
        "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "token_registry",
        "tags": ["wrapped", "eth"],
    },
    # Sanctions (OFAC)
    {
        "name": "OFAC: Sanctioned Entity A",
        "entity_type": EntityType.SANCTIONED,
        "address": "0x0000000000000000000000000000000000001015",
        "chain": "Ethereum",
        "confidence": ConfidenceLevel.CONFIRMED,
        "source": "ofac_sdn",
        "tags": ["sanctions", "ofac", "high_risk"],
    },
]

# ============================================================
# DEMO USERS
# ============================================================

#: Password every seeded demo account shares. These are synthetic accounts in a
#: local demo database; the seeder is never run against production (it writes
#: SYNTHETIC_MARKER-tagged rows). `users.hashed_password` is NOT NULL, so a
#: value has to be supplied here or the whole seed transaction aborts.
DEMO_USER_PASSWORD = "tracex-demo-password"

DEMO_USERS = [
    {
        "email": "analyst.a@tracex.gov",
        "full_name": "Analyst A",
        "role": UserRole.ANALYST,
        "is_active": True,
    },
    {
        "email": "analyst.b@tracex.gov",
        "full_name": "Analyst B",
        "role": UserRole.ANALYST,
        "is_active": True,
    },
    {
        "email": "supervisor@tracex.gov",
        "full_name": "Supervisor",
        "role": UserRole.SUPERVISOR,
        "is_active": True,
    },
    {
        "email": "admin@tracex.gov",
        "full_name": "Administrator",
        "role": UserRole.ADMIN,
        "is_active": True,
    },
]


async def seed_database():
    """Seed PostgreSQL with demo data."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Re-seeding is idempotent, the same way the Neo4j half is. Without
        # this a second run dies on the users.email / cases.case_number unique
        # constraints, leaving a half-written database behind.
        #
        # Demo cases are deleted and rebuilt -- that cascades to their wallets,
        # transactions, investigation runs and reports (all ON DELETE CASCADE).
        await session.execute(
            delete(Case).where(Case.case_number.in_([c["case_number"] for c in DEMO_CASES]))
        )
        await session.flush()

        # Demo users are *upserted*, not deleted and recreated. They are
        # referenced by rows this seeder does not own -- audit_log.actor_id
        # from any login, reports.generated_by for reports raised against
        # non-demo cases -- and neither FK cascades, so deleting the users
        # fails with a ForeignKeyViolationError. Updating in place keeps every
        # existing reference valid.
        demo_password_hash = hash_password(DEMO_USER_PASSWORD)
        demo_emails = [u["email"] for u in DEMO_USERS]
        existing_users = (
            (await session.execute(select(User).where(User.email.in_(demo_emails)))).scalars().all()
        )
        by_email = {u.email: u for u in existing_users}

        user_map = {}
        created = 0
        for udata in DEMO_USERS:
            user = by_email.get(udata["email"])
            if user is None:
                user = User(id=uuid4(), email=udata["email"])
                session.add(user)
                created += 1
            user.full_name = udata["full_name"]
            user.hashed_password = demo_password_hash
            user.role = udata["role"]
            user.is_active = udata["is_active"]
            user_map[udata["email"]] = user
        await session.flush()
        print(
            f"Seeded {len(user_map)} demo users ({created} created, {len(user_map) - created} updated)"
        )

        # Create cases with wallets and transactions
        case_map = {}
        wallet_map = {}

        for cdata in DEMO_CASES:
            # Find assigned user
            assigned_user = user_map.get("analyst.a@tracex.gov")

            case = Case(
                id=uuid4(),
                case_number=cdata["case_number"],
                title=cdata["title"],
                crime_type=cdata["crime_type"],
                description=cdata["description"],
                status=cdata["status"],
                assigned_to=assigned_user.id if assigned_user else None,
            )
            session.add(case)
            await session.flush()
            case_map[cdata["case_number"]] = case
            print(f"Created case: {cdata['case_number']} - {cdata['title']}")

            # Create wallets
            case_wallets = []
            for idx, wdata in enumerate(cdata["wallets"]):
                wallet = Wallet(
                    id=uuid4(),
                    case_id=case.id,
                    address=wdata["address"],
                    chain=wdata["chain"],
                    label=wdata["label"],
                    attribution_status=wdata["attribution_status"],
                    risk_score=Decimal(str(wdata["risk_score"])),
                    entity_name=wdata.get("entity_name"),
                    entity_confidence=wdata.get("entity_confidence"),
                    wallet_metadata={"source": SYNTHETIC_MARKER, "demo_index": idx},
                )
                session.add(wallet)
                case_wallets.append(wallet)
                wallet_key = f"{cdata['case_number']}:{idx}"
                wallet_map[wallet_key] = wallet
            await session.flush()

            # Create transactions
            for tdata in cdata.get("transactions", []):
                from_wallet = case_wallets[tdata["from_idx"]]
                to_wallet = case_wallets[tdata["to_idx"]]

                tx = Transaction(
                    id=uuid4(),
                    wallet_id=from_wallet.id,
                    tx_hash=f"0x{uuid4().hex[:64]}",
                    block_number=random.randint(18000000, 19500000),
                    timestamp=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                    from_address=from_wallet.address,
                    to_address=to_wallet.address,
                    value=str(int(tdata["value_eth"] * 1e18)),
                    value_usd=Decimal(str(tdata["value_eth"] * 2500)),
                    token_symbol="ETH",
                    method=tdata["method"],
                    is_suspicious=tdata["suspicious"],
                    transaction_metadata={"source": SYNTHETIC_MARKER},
                )
                session.add(tx)

                # One row per on-chain transaction, owned by the sending
                # wallet. A mirrored row for `to_wallet` used to be inserted
                # here reusing the same tx_hash, which violates the unique
                # ix_transactions_tx_hash index (a transaction hash is globally
                # unique on-chain) and aborted the whole seed. The receiving
                # side of a transfer is reachable via `to_address`, and the
                # Neo4j seed below models both directions explicitly with
                # SENT/RECEIVED relationships.

        # Create investigation runs
        for cdata in DEMO_CASES:
            case = case_map[cdata["case_number"]]
            case_wallets = [w for w in wallet_map.values() if w.case_id == case.id]

            for idx, wallet in enumerate(case_wallets[:3]):  # First 3 wallets per case
                status = (
                    InvestigationStatus.COMPLETED
                    if idx == 0
                    else (InvestigationStatus.RUNNING if idx == 1 else InvestigationStatus.PENDING)
                )

                inv = InvestigationRun(
                    id=uuid4(),
                    case_id=case.id,
                    wallet_id=wallet.id,
                    status=status,
                    started_at=datetime.utcnow() - timedelta(hours=random.randint(1, 48)),
                    completed_at=datetime.utcnow() - timedelta(hours=random.randint(0, 12))
                    if status == InvestigationStatus.COMPLETED
                    else None,
                    config={"trace_depth": 5, "max_transactions": 1000, "demo": True},
                    result_summary={
                        "transactions_found": random.randint(50, 500),
                        "unique_addresses": random.randint(10, 100),
                        "total_value_eth": str(random.randint(100, 50000)),
                        "chains_analyzed": [wallet.chain],
                        "demo": True,
                    }
                    if status == InvestigationStatus.COMPLETED
                    else None,
                )
                session.add(inv)

        # Create reports
        for cdata in DEMO_CASES:
            if cdata["status"] in [CaseStatus.CLOSED, CaseStatus.IN_PROGRESS]:
                case = case_map[cdata["case_number"]]
                report = Report(
                    id=uuid4(),
                    case_id=case.id,
                    title=f"{cdata['title']} - Investigation Report",
                    summary=f"Comprehensive analysis of {cdata['crime_type'].value} case involving {len([w for w in wallet_map.values() if w.case_id == case.id])} wallets.",
                    findings={
                        "executive_summary": f"Case {cdata['case_number']} involved tracing funds through multiple wallets and exchanges.",
                        "key_findings": [
                            f"Identified {random.randint(1, 3)} confirmed VASP endpoints",
                            f"Detected {random.randint(0, 2)} mixer interactions",
                            f"Traced ${random.randint(1, 50)}M in total value",
                        ],
                    },
                    risk_assessment={
                        "overall_risk": "HIGH",
                        "average_score": 72.5,
                        "critical_wallets": 2,
                    },
                    generated_by=user_map["analyst.a@tracex.gov"].id,
                    format="pdf",
                )
                session.add(report)

        await session.commit()
        print("Database seeding completed!")


async def seed_neo4j():
    """Seed Neo4j with demo graph data."""
    await Neo4jClient.initialize()

    async with Neo4jClient.session() as session:
        # Clear existing demo data so re-running the seeder is idempotent.
        # `metadata` is stored as a JSON *string* (Neo4j property values can
        # only be primitives or arrays, so a nested map cannot be written at
        # all -- see _dump_metadata in src/graph/repository.py). The previous
        # `n.metadata.source = $marker` map access therefore raised a
        # CypherTypeError and never deleted anything; substring-match the
        # serialized marker instead.
        await session.run(
            "MATCH (n) WHERE n.metadata IS NOT NULL AND n.metadata CONTAINS $marker "
            "DETACH DELETE n",
            marker=SYNTHETIC_MARKER,
        )

        # Create wallets
        for cdata in DEMO_CASES:
            for _idx, wdata in enumerate(cdata["wallets"]):
                wallet = GraphWallet(
                    address=wdata["address"],
                    chain=wdata["chain"],
                    label=wdata["label"],
                    risk_score=wdata["risk_score"],
                    first_seen=datetime.utcnow() - timedelta(days=30),
                    last_seen=datetime.utcnow(),
                    total_sent=random.randint(10, 10000),
                    total_received=random.randint(10, 10000),
                    tx_count=random.randint(5, 500),
                    entity_name=wdata.get("entity_name"),
                    entity_type=EntityType.EXCHANGE
                    if wdata.get("entity_name")
                    else EntityType.UNKNOWN,
                    entity_confidence=ConfidenceLevel(wdata["entity_confidence"])
                    if wdata.get("entity_confidence")
                    else ConfidenceLevel.UNKNOWN,
                    metadata={"source": SYNTHETIC_MARKER, "case_number": cdata["case_number"]},
                )
                await graph_repository.upsert_wallet(wallet)

                # Link to entity if attributed
                if wdata.get("entity_name") and wdata.get("entity_confidence"):
                    entity = GraphEntity(
                        name=wdata["entity_name"],
                        entity_type=EntityType.EXCHANGE,
                        address=wdata["address"],
                        chain=wdata["chain"],
                        confidence=ConfidenceLevel(wdata["entity_confidence"]),
                        source="analysis",
                        tags=["demo"],
                        metadata={"source": SYNTHETIC_MARKER},
                    )
                    await graph_repository.upsert_entity(entity)
                    await graph_repository.link_wallet_entity(
                        wdata["address"], wdata["chain"], wdata["address"]
                    )

        # Create entities
        for edata in DEMO_ENTITIES:
            entity = GraphEntity(
                name=edata["name"],
                entity_type=edata["entity_type"],
                address=edata["address"],
                chain=edata["chain"],
                confidence=edata["confidence"],
                source=edata["source"],
                tags=edata["tags"],
                metadata={"source": SYNTHETIC_MARKER},
            )
            await graph_repository.upsert_entity(entity)

        # Create transactions and links
        for cdata in DEMO_CASES:
            case_wallets = list(cdata["wallets"])
            for tdata in cdata.get("transactions", []):
                from_w = case_wallets[tdata["from_idx"]]
                to_w = case_wallets[tdata["to_idx"]]

                tx = GraphTransaction(
                    tx_hash=f"0x{uuid4().hex[:64]}",
                    chain=from_w["chain"],
                    block_number=random.randint(18000000, 19500000),
                    timestamp=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                    from_address=from_w["address"],
                    to_address=to_w["address"],
                    value=str(int(tdata["value_eth"] * 1e18)),
                    value_usd=tdata["value_eth"] * 2500,
                    token_symbol="ETH",
                    method=tdata["method"],
                    is_suspicious=tdata["suspicious"],
                    metadata={"source": SYNTHETIC_MARKER, "case_number": cdata["case_number"]},
                )
                await graph_repository.upsert_transaction(tx)
                await graph_repository.link_wallet_transaction(
                    from_w["address"], from_w["chain"], tx.tx_hash, "sent"
                )
                await graph_repository.link_wallet_transaction(
                    to_w["address"], to_w["chain"], tx.tx_hash, "received"
                )

    print("Neo4j seeding completed!")


async def main():
    print("=" * 60)
    print("TRACE-X Demo Data Seeder")
    print("=" * 60)
    print("Seeding SYNTHETIC demo data for SIH 2026 demonstration")
    print("=" * 60)

    await seed_database()
    await seed_neo4j()

    print("=" * 60)
    print("All demo data seeded successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
