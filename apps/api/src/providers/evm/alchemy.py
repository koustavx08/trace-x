from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx
import structlog

from .base import EVMProvider
from ..base import BlockchainTransaction, WalletBalance

logger = structlog.get_logger(__name__)


class AlchemyProvider(EVMProvider):
    def __init__(
        self,
        rpc_url: str,
        api_key: str,
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
        self._alchemy_url = f"https://{chain_name.lower()}-mainnet.g.alchemy.com/v2/{api_key}"
        self._api_key = api_key

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
                "fromAddress": checksum_addr,
                "category": ["external", "internal", "erc20", "erc721", "erc1155"],
                "maxCount": min(page_size, 1000),
                "pageKey": None,
            }

            if start_block > 0:
                params["fromBlock"] = hex(start_block)
            if end_block:
                params["toBlock"] = hex(end_block)

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [params],
            }

            response = await self._http_client.post(self._alchemy_url, json=payload)
            response.raise_for_status()
            data = response.json()

            transfers = data.get("result", {}).get("transfers", [])
            transactions = []

            for transfer in transfers:
                tx = BlockchainTransaction(
                    tx_hash=transfer.get("hash", ""),
                    block_number=int(transfer.get("blockNum", "0"), 16) if transfer.get("blockNum") else 0,
                    timestamp=datetime.fromisoformat(transfer.get("metadata", {}).get("blockTimestamp", "").replace("Z", "+00:00")) if transfer.get("metadata", {}).get("blockTimestamp") else datetime.utcnow(),
                    from_address=transfer.get("from", ""),
                    to_address=transfer.get("to", ""),
                    value=str(transfer.get("value", 0)),
                    value_usd=transfer.get("value") * transfer.get("erc20Metadata", {}).get("price", 0) if transfer.get("erc20Metadata", {}).get("price") else None,
                    token_address=transfer.get("rawContract", {}).get("address") if transfer.get("category") in ["erc20", "erc721", "erc1155"] else None,
                    token_symbol=transfer.get("erc20Metadata", {}).get("symbol") if transfer.get("erc20Metadata") else None,
                    token_decimals=transfer.get("erc20Metadata", {}).get("decimals") if transfer.get("erc20Metadata") else None,
                    method=transfer.get("function", None),
                    metadata={"alchemy_category": transfer.get("category")},
                )
                transactions.append(tx)

            return transactions

        except Exception as e:
            logger.warning("alchemy_get_transactions_failed", address=address, error=str(e))
            return []

    async def get_token_transfers(
        self,
        address: str,
        token_address: Optional[str] = None,
        start_block: int = 0,
        end_block: Optional[int] = None,
    ) -> List[BlockchainTransaction]:
        try:
            checksum_addr = self._to_checksum_address(address)

            params = {
                "fromAddress": checksum_addr,
                "category": ["erc20"],
                "maxCount": 1000,
            }

            if token_address:
                params["contractAddresses"] = [self._to_checksum_address(token_address)]

            if start_block > 0:
                params["fromBlock"] = hex(start_block)
            if end_block:
                params["toBlock"] = hex(end_block)

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [params],
            }

            response = await self._http_client.post(self._alchemy_url, json=payload)
            response.raise_for_status()
            data = response.json()

            transfers = data.get("result", {}).get("transfers", [])
            transactions = []

            for transfer in transfers:
                tx = BlockchainTransaction(
                    tx_hash=transfer.get("hash", ""),
                    block_number=int(transfer.get("blockNum", "0"), 16) if transfer.get("blockNum") else 0,
                    timestamp=datetime.fromisoformat(transfer.get("metadata", {}).get("blockTimestamp", "").replace("Z", "+00:00")) if transfer.get("metadata", {}).get("blockTimestamp") else datetime.utcnow(),
                    from_address=transfer.get("from", ""),
                    to_address=transfer.get("to", ""),
                    value=str(transfer.get("value", 0)),
                    value_usd=transfer.get("value") * transfer.get("erc20Metadata", {}).get("price", 0) if transfer.get("erc20Metadata", {}).get("price") else None,
                    token_address=transfer.get("rawContract", {}).get("address"),
                    token_symbol=transfer.get("erc20Metadata", {}).get("symbol"),
                    token_decimals=transfer.get("erc20Metadata", {}).get("decimals"),
                    metadata={"alchemy_category": "erc20"},
                )
                transactions.append(tx)

            return transactions

        except Exception as e:
            logger.warning("alchemy_get_token_transfers_failed", address=address, error=str(e))
            return []

    async def get_wallet_balance(self, address: str) -> WalletBalance:
        try:
            checksum_addr = self._to_checksum_address(address)

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getTokenBalances",
                "params": [checksum_addr, "erc20"],
            }

            response = await self._http_client.post(self._alchemy_url, json=payload)
            response.raise_for_status()
            data = response.json()

            token_balances = data.get("result", {}).get("tokenBalances", [])
            tokens = []

            for token in token_balances:
                if int(token.get("tokenBalance", "0"), 16) > 0:
                    tokens.append({
                        "contract_address": token.get("contractAddress"),
                        "symbol": token.get("symbol"),
                        "name": token.get("name"),
                        "decimals": token.get("decimals"),
                        "balance": token.get("tokenBalance"),
                    })

            eth_balance_wei = self._w3.eth.get_balance(checksum_addr)
            eth_balance = self._w3.from_wei(eth_balance_wei, "ether")

            return WalletBalance(
                address=address,
                chain=self._chain_name,
                eth_balance=str(eth_balance),
                tokens=tokens,
                last_updated=datetime.utcnow(),
            )

        except Exception as e:
            logger.warning("alchemy_get_wallet_balance_failed", address=address, error=str(e))
            return await super().get_wallet_balance(address)