from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import httpx
import structlog

from .base import EVMProvider
from ..base import BlockchainTransaction, WalletBalance

logger = structlog.get_logger(__name__)

# keccak256("Transfer(address,address,uint256)")
ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


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

    def _pad_topic(self, address: str) -> str:
        addr = address.lower().replace("0x", "")
        return "0x" + "0" * 24 + addr

    def _topic_to_address(self, topic: str) -> str:
        return self._to_checksum_address("0x" + topic[-40:])

    async def _eth_get_logs(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_getLogs",
            "params": [params],
        }
        response = await self._http_client.post(self._rpc_url, json=payload)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", "eth_getLogs error"))
        return data.get("result", [])

    def _log_to_transaction(self, log: Dict[str, Any]) -> BlockchainTransaction:
        topics = log.get("topics", [])
        from_addr = self._topic_to_address(topics[1]) if len(topics) > 1 else ""
        to_addr = self._topic_to_address(topics[2]) if len(topics) > 2 else ""
        raw_data = log.get("data") or "0x0"
        try:
            value = str(int(raw_data, 16))
        except ValueError:
            value = "0"

        return BlockchainTransaction(
            tx_hash=log.get("transactionHash", ""),
            block_number=int(log.get("blockNumber", "0x0"), 16),
            # eth_getLogs does not return block timestamps; a per-log
            # eth_getBlockByNumber call would be needed for exact timestamps,
            # which is deliberately avoided here to keep this bounded to a
            # small, predictable number of RPC calls per request.
            timestamp=datetime.utcnow(),
            from_address=from_addr,
            to_address=to_addr,
            value=value,
            token_address=log.get("address"),
            method="transfer",
            metadata={"log_index": log.get("logIndex"), "source": "eth_getLogs"},
        )

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

            # Sanity-check the address / RPC connectivity.
            count_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getTransactionCount",
                "params": [checksum_addr, "latest"],
            }
            count_response = await self._http_client.post(self._rpc_url, json=count_payload)
            count_response.raise_for_status()
            count_data = count_response.json()
            if "error" in count_data:
                raise RuntimeError(count_data["error"].get("message", "eth_getTransactionCount error"))

            # Plain Infura JSON-RPC has no address-indexed transaction-history
            # endpoint (unlike Alchemy's alchemy_getAssetTransfers). The best
            # available approximation without a third-party indexer is to
            # derive transaction hashes from ERC20/721 Transfer event logs
            # involving this address, then fetch full transaction details for
            # each hash. Pure native-ETH transfers that never touch a token
            # contract are not discoverable this way; use the Alchemy
            # provider (or a dedicated indexer) when that matters.
            transfer_logs = await self.get_token_transfers(
                checksum_addr, start_block=start_block, end_block=end_block
            )

            seen: set = set()
            tx_hashes: List[str] = []
            for tx in transfer_logs:
                if tx.tx_hash and tx.tx_hash not in seen:
                    seen.add(tx.tx_hash)
                    tx_hashes.append(tx.tx_hash)

            offset = (page - 1) * page_size
            page_hashes = tx_hashes[offset: offset + page_size]

            transactions = [
                tx for tx in await asyncio.gather(*(self.get_transaction(h) for h in page_hashes))
                if tx is not None
            ]

            return transactions

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
        try:
            checksum_addr = self._to_checksum_address(address)
            topic_addr = self._pad_topic(checksum_addr)

            from_block = hex(start_block) if start_block > 0 else "0x0"
            to_block = hex(end_block) if end_block else "latest"

            base_params: Dict[str, Any] = {"fromBlock": from_block, "toBlock": to_block}
            if token_address:
                base_params["address"] = self._to_checksum_address(token_address)

            sent_params = {**base_params, "topics": [ERC20_TRANSFER_TOPIC, topic_addr, None]}
            received_params = {**base_params, "topics": [ERC20_TRANSFER_TOPIC, None, topic_addr]}

            sent_logs, received_logs = await asyncio.gather(
                self._eth_get_logs(sent_params),
                self._eth_get_logs(received_params),
            )

            logs_by_hash: Dict[str, Dict[str, Any]] = {}
            for log in [*sent_logs, *received_logs]:
                tx_hash = log.get("transactionHash")
                if tx_hash:
                    logs_by_hash[tx_hash] = log

            return [self._log_to_transaction(log) for log in logs_by_hash.values()]

        except Exception as e:
            logger.warning("infura_get_token_transfers_failed", address=address, error=str(e))
            return []

    async def get_wallet_balance(self, address: str) -> WalletBalance:
        return await super().get_wallet_balance(address)
