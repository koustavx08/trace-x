from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx
import structlog

from .base import EVMProvider
from ..base import BlockchainTransaction, WalletBalance

logger = structlog.get_logger(__name__)


class InfuraProvider(EVMProvider):
    def __init__(
        self,
        rpc_url: str,
        api_key: str,
        api_secret: Optional[str],
        chain_id: int,
        chain_name: str,
        symbol: str,
        explorer_url: str,
        timeout: float = 30.0,
    ):
        super().__init__(
            rpc_url=rpc_url,
            chain_id=chain_id,
            chain_name=chain_name,
            symbol=symbol,
            explorer_url=explorer_url,
            api_key=api_key,
            timeout=timeout,
        )
        self._api_key = api_key
        self._api_secret = api_secret
        self._auth = (api_key, api_secret) if api_secret else None

    async def get_transactions_by_address(
        self,
        address: str,
        start_block: int = 0,
        end_block: Optional[int] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> List[BlockchainTransaction]:
        try:
            checksum_addr = self._to_checksum_address(address)

            params = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getTransactionCount",
                "params": [checksum_addr, "latest"],
            }

            response = await self._http_client.post(self._rpc_url, json=params)
            response.raise_for_status()

            return []

        except Exception as e:
            logger.warning("infura_get_transactions_failed", address=address, error=str(e))
            return []

    async def get_token_transfers(
        self,
        address: str,
        token_address: Optional[str] = None,
        start_block: int = 0,
        end_block: Optional[int] = None,
    ) -> List[BlockchainTransaction]:
        return []

    async def get_wallet_balance(self, address: str) -> WalletBalance:
        return await super().get_wallet_balance(address)