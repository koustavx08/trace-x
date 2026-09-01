from abc import abstractmethod
from datetime import datetime
from typing import Any

import httpx
import structlog
from web3 import Web3

from ..base import (
    BlockchainProvider,
    BlockchainTransaction,
    ChainInfo,
    WalletBalance,
)

logger = structlog.get_logger(__name__)


class EVMProvider(BlockchainProvider):
    def __init__(
        self,
        rpc_url: str,
        chain_id: int,
        chain_name: str,
        symbol: str,
        explorer_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self._rpc_url = rpc_url
        self._chain_id = chain_id
        self._chain_name = chain_name
        self._symbol = symbol
        self._explorer_url = explorer_url
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries

        self._w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout}))
        self._http_client = httpx.AsyncClient(timeout=timeout)

    @property
    def chain_id(self) -> int:
        return self._chain_id

    @property
    def chain_name(self) -> str:
        return self._chain_name

    def _to_checksum_address(self, address: str) -> str:
        return Web3.to_checksum_address(address)

    def _is_valid_address(self, address: str) -> bool:
        try:
            return Web3.is_address(address)
        except Exception:
            return False

    async def get_latest_block(self) -> int:
        return self._w3.eth.block_number

    async def get_block(self, block_number: int) -> dict[str, Any] | None:
        try:
            block = self._w3.eth.get_block(block_number, full_transactions=False)
            return dict(block) if block else None
        except Exception as e:
            logger.warning("get_block_failed", block_number=block_number, error=str(e))
            return None

    async def get_transaction(self, tx_hash: str) -> BlockchainTransaction | None:
        try:
            tx = self._w3.eth.get_transaction(tx_hash)
            if not tx:
                return None

            receipt = self._w3.eth.get_transaction_receipt(tx_hash)

            return BlockchainTransaction(
                tx_hash=tx_hash,
                block_number=tx.blockNumber,
                timestamp=datetime.utcfromtimestamp(
                    self._w3.eth.get_block(tx.blockNumber).timestamp
                ),
                from_address=tx["from"],
                to_address=tx.to or "",
                value=str(tx.value),
                gas_used=receipt.gasUsed if receipt else None,
                gas_price=str(tx.gasPrice) if tx.gasPrice else None,
                status=receipt.status if receipt else 1,
                method=tx.input[:10] if tx.input and tx.input != "0x" else None,
            )
        except Exception as e:
            logger.warning("get_transaction_failed", tx_hash=tx_hash, error=str(e))
            return None

    @abstractmethod
    async def get_transactions_by_address(
        self,
        address: str,
        start_block: int = 0,
        end_block: int | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[BlockchainTransaction]:
        pass

    async def get_wallet_balance(self, address: str) -> WalletBalance:
        try:
            checksum_addr = self._to_checksum_address(address)
            balance_wei = self._w3.eth.get_balance(checksum_addr)
            balance_eth = self._w3.from_wei(balance_wei, "ether")

            return WalletBalance(
                address=address,
                chain=self._chain_name,
                eth_balance=str(balance_eth),
                tokens=[],
                last_updated=datetime.utcnow(),
            )
        except Exception as e:
            logger.warning("get_wallet_balance_failed", address=address, error=str(e))
            return WalletBalance(
                address=address,
                chain=self._chain_name,
                eth_balance="0",
                tokens=[],
                last_updated=datetime.utcnow(),
            )

    @abstractmethod
    async def get_token_transfers(
        self,
        address: str,
        token_address: str | None = None,
        start_block: int = 0,
        end_block: int | None = None,
    ) -> list[BlockchainTransaction]:
        pass

    async def validate_address(self, address: str) -> bool:
        return self._is_valid_address(address)

    async def get_chain_info(self) -> ChainInfo:
        return ChainInfo(
            chain_id=self._chain_id,
            name=self._chain_name,
            symbol=self._symbol,
            rpc_url=self._rpc_url,
            explorer_url=self._explorer_url,
        )

    async def health_check(self) -> bool:
        try:
            block = await self.get_latest_block()
            return block > 0
        except Exception:
            return False

    async def close(self) -> None:
        await self._http_client.aclose()
