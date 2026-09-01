from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
import structlog

from src.core import get_session_context, get_logger, NotFoundError, ValidationError
from src.core.validation import is_valid_evm_address, to_checksum, get_chain_info
from src.models import Wallet, Case, Transaction, InvestigationRun, InvestigationStatus
from src.schemas import WalletCreate, WalletResponse, InvestigationRunCreate, InvestigationRunResponse
from ..providers import ProviderFactory, BlockchainTransaction

logger = get_logger(__name__)


class WalletAnalysisService:
    def __init__(self):
        ProviderFactory.initialize()

    async def validate_and_create_wallet(
        self,
        case_id: UUID,
        address: str,
        chain_id: Optional[int] = None,
        label: Optional[str] = None,
    ) -> WalletResponse:
        async with get_session_context() as session:
            case = await session.get(Case, case_id)
            if not case:
                raise NotFoundError("Case", str(case_id))

            if not is_valid_evm_address(address):
                raise ValidationError(f"Invalid EVM address: {address}")

            checksum_addr = to_checksum(address)

            if chain_id is None:
                chain_id = 1

            chain_info = get_chain_info(chain_id)
            if not chain_info:
                raise ValidationError(f"Unsupported chain ID: {chain_id}")

            provider = ProviderFactory.get_provider(chain_id)
            if not provider:
                raise ValidationError(f"No provider configured for chain ID: {chain_id}")

            is_valid = await provider.validate_address(checksum_addr)
            if not is_valid:
                raise ValidationError(f"Address validation failed on chain: {chain_info['name']}")

            existing = await session.execute(
                session.query(Wallet).filter(
                    Wallet.case_id == case_id,
                    Wallet.address == checksum_addr,
                    Wallet.chain == chain_info["name"],
                )
            )
            if existing.scalar_one_or_none():
                raise ValidationError(f"Wallet already tracked in this case: {checksum_addr}")

            balance = await provider.get_wallet_balance(checksum_addr)

            wallet = Wallet(
                case_id=case_id,
                address=checksum_addr,
                chain=chain_info["name"],
                label=label or "Suspect Wallet",
                attribution_status="unverified",
                risk_score=0.0,
                metadata={
                    "eth_balance": balance.eth_balance,
                    "token_count": len(balance.tokens),
                    "last_balance_check": balance.last_updated.isoformat() if balance.last_updated else None,
                },
            )
            session.add(wallet)
            await session.flush()
            await session.refresh(wallet)

            logger.info(
                "wallet_created",
                wallet_id=str(wallet.id),
                case_id=str(case_id),
                address=checksum_addr,
                chain=chain_info["name"],
            )

            return WalletResponse.model_validate(wallet)

    async def analyze_wallet(
        self,
        wallet_id: UUID,
        trace_depth: int = 5,
        max_transactions: int = 1000,
    ) -> InvestigationRunResponse:
        async with get_session_context() as session:
            wallet = await session.get(Wallet, wallet_id)
            if not wallet:
                raise NotFoundError("Wallet", str(wallet_id))

            case = await session.get(Case, wallet.case_id)
            if not case:
                raise NotFoundError("Case", str(wallet.case_id))

            chain_id = self._get_chain_id(wallet.chain)
            provider = ProviderFactory.get_provider(chain_id)
            if not provider:
                raise ValidationError(f"No provider for chain: {wallet.chain}")

            investigation = InvestigationRun(
                case_id=wallet.case_id,
                wallet_id=wallet_id,
                status=InvestigationStatus.RUNNING,
                config={
                    "trace_depth": trace_depth,
                    "max_transactions": max_transactions,
                    "started_at": datetime.utcnow().isoformat(),
                },
            )
            session.add(investigation)
            await session.flush()
            await session.refresh(investigation)

            try:
                transactions = await provider.get_transactions_by_address(
                    wallet.address,
                    start_block=0,
                    end_block=None,
                    page=1,
                    page_size=max_transactions,
                )

                for tx in transactions:
                    db_tx = Transaction(
                        wallet_id=wallet_id,
                        tx_hash=tx.tx_hash,
                        block_number=tx.block_number,
                        timestamp=tx.timestamp,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        value=tx.value,
                        value_usd=tx.value_usd,
                        token_address=tx.token_address,
                        token_symbol=tx.token_symbol,
                        method=tx.method,
                        is_suspicious=False,
                        metadata=tx.metadata,
                    )
                    session.add(db_tx)

                investigation.status = InvestigationStatus.COMPLETED
                investigation.completed_at = datetime.utcnow()
                investigation.result_summary = {
                    "transactions_found": len(transactions),
                    "unique_addresses": len(set([tx.from_address for tx in transactions] + [tx.to_address for tx in transactions])),
                    "total_value_eth": str(sum(int(tx.value) for tx in transactions if tx.value.isdigit())),
                    "chains_analyzed": [wallet.chain],
                }

                wallet.metadata = wallet.metadata or {}
                wallet.metadata["last_analysis"] = datetime.utcnow().isoformat()
                wallet.metadata["transactions_analyzed"] = len(transactions)

                await session.flush()
                await session.refresh(investigation)

                logger.info(
                    "wallet_analysis_completed",
                    investigation_id=str(investigation.id),
                    wallet_id=str(wallet_id),
                    transactions_found=len(transactions),
                )

                return InvestigationRunResponse.model_validate(investigation)

            except Exception as e:
                investigation.status = InvestigationStatus.FAILED
                investigation.error_message = str(e)
                investigation.completed_at = datetime.utcnow()
                await session.flush()
                await session.refresh(investigation)

                logger.error(
                    "wallet_analysis_failed",
                    investigation_id=str(investigation.id),
                    wallet_id=str(wallet_id),
                    error=str(e),
                )

                return InvestigationRunResponse.model_validate(investigation)

    async def trace_fund_flow(
        self,
        wallet_id: UUID,
        max_hops: int = 5,
        min_value_eth: float = 0.001,
    ) -> Dict[str, Any]:
        async with get_session_context() as session:
            wallet = await session.get(Wallet, wallet_id)
            if not wallet:
                raise NotFoundError("Wallet", str(wallet_id))

            chain_id = self._get_chain_id(wallet.chain)
            provider = ProviderFactory.get_provider(chain_id)
            if not provider:
                raise ValidationError(f"No provider for chain: {wallet.chain}")

            visited = set()
            queue = [(wallet.address, 0, [])]
            paths = []
            edges = []

            while queue and len(visited) < 1000:
                current_addr, hop, path = queue.pop(0)

                if current_addr in visited or hop >= max_hops:
                    continue

                visited.add(current_addr)

                txs = await provider.get_transactions_by_address(
                    current_addr,
                    page=1,
                    page_size=100,
                )

                for tx in txs:
                    value_eth = int(tx.value) / 1e18 if tx.value.isdigit() else 0
                    if value_eth < min_value_eth:
                        continue

                    edges.append({
                        "from": tx.from_address,
                        "to": tx.to_address,
                        "value": tx.value,
                        "value_eth": value_eth,
                        "tx_hash": tx.tx_hash,
                        "block": tx.block_number,
                        "timestamp": tx.timestamp.isoformat(),
                        "hop": hop,
                    })

                    if tx.to_address not in visited and hop + 1 < max_hops:
                        new_path = path + [tx.to_address]
                        queue.append((tx.to_address, hop + 1, new_path))
                        paths.append({
                            "path": new_path,
                            "length": len(new_path),
                            "total_value_eth": sum(
                                int(e["value"]) / 1e18 for e in edges if e["to"] in new_path
                            ),
                        })

            return {
                "root_address": wallet.address,
                "wallets_traced": len(visited),
                "edges": edges,
                "paths": paths[:50],
                "max_hops_reached": max(e["hop"] for e in edges) if edges else 0,
            }

    def _get_chain_id(self, chain_name: str) -> int:
        chain_map = {
            "Ethereum": 1,
            "Polygon": 137,
            "BSC": 56,
            "Arbitrum": 42161,
            "Optimism": 10,
            "Base": 8453,
        }
        return chain_map.get(chain_name, 1)


wallet_analysis_service = WalletAnalysisService()