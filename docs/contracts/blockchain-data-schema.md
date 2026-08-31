# Blockchain Data Schema

> **Status:** Baseline reference (pre-parallel-merge). Derived from `apps/api/src/providers/base.py`,
> `apps/api/src/providers/factory.py`, `apps/api/src/providers/evm/alchemy.py`, `apps/api/src/providers/evm/infura.py`.
> **Caveat:** WS3 adds `providers/chainalysis.py`, `providers/ciphertrace.py`, a new `ProviderNotConfiguredError`, and
> fixes `infura.py`'s `get_transactions_by_address`/`get_token_transfers` (currently stubbed, see below). Re-verify the
> provider list and error-handling behavior once WS3 lands.

## `BlockchainProvider` interface (`providers/base.py`)

Abstract base every chain integration implements:

```python
class BlockchainProvider(ABC):
    chain_id: int              # property
    chain_name: str            # property
    async def get_latest_block() -> int
    async def get_block(block_number: int) -> Optional[Dict[str, Any]]
    async def get_transaction(tx_hash: str) -> Optional[BlockchainTransaction]
    async def get_transactions_by_address(address, start_block=0, end_block=None, page=1, page_size=100) -> List[BlockchainTransaction]
    async def get_wallet_balance(address: str) -> WalletBalance
    async def get_token_transfers(address, token_address=None, start_block=0, end_block=None) -> List[BlockchainTransaction]
    async def validate_address(address: str) -> bool
    async def get_chain_info() -> ChainInfo
    async def health_check() -> bool
    async def close() -> None
```

## Data classes

### `BlockchainTransaction`

```python
tx_hash: str
block_number: int
timestamp: datetime
from_address: str
to_address: str
value: str                     # wei, as string (avoids float precision loss)
value_usd: float | None
token_address: str | None
token_symbol: str | None
token_decimals: int | None
method: str | None
gas_used: int | None
gas_price: str | None
status: int = 1
metadata: dict | None
```

### `WalletBalance`

```python
address: str
chain: str
eth_balance: str
eth_balance_usd: float | None
tokens: list[dict]
last_updated: datetime | None
```

### `ChainInfo`

```python
chain_id: int
name: str
symbol: str
rpc_url: str
explorer_url: str
is_testnet: bool = False
```

## `ProviderRegistry` / `ProviderFactory`

`ProviderRegistry` (in `base.py`) is a class-level `{chain_id: BlockchainProvider}` map with a "default provider"
pointer. `ProviderFactory.initialize()` (in `factory.py`) is idempotent (guarded by `_initialized`) and, driven by
`Settings`:

- If `ALCHEMY_API_KEY` is set: registers Alchemy providers for Ethereum (`chain_id=1`) and Polygon (`chain_id=137`),
  and sets Ethereum-Alchemy as the default provider.
- If `INFURA_API_KEY` is set: registers Infura providers for the same two chains, but **only if a provider for that
  chain isn't already registered** (Alchemy wins on chain-id collision — Infura acts as a secondary/fallback provider
  registered second, not tried second at request time).
- If neither key is set: `ProviderRegistry` stays empty. Any code path calling `ProviderFactory.get_provider(chain_id)`
  gets back `None`, and callers are expected to raise their own `ValidationError` (see `services/wallet_analysis.py`) —
  there is no dedicated "provider not configured" exception type in the baseline tree. WS3 adds
  `ProviderNotConfiguredError` for this case.

## Configured providers (baseline)

| Provider | File | Status |
|---|---|---|
| Alchemy (Ethereum, Polygon) | `providers/evm/alchemy.py` | Implemented; requires `ALCHEMY_API_KEY` |
| Infura (Ethereum, Polygon) | `providers/evm/infura.py` | **Partially stubbed** — `get_transactions_by_address` discards its own RPC result and returns `[]`; `get_token_transfers` unconditionally returns `[]`. WS3 fixes both. |
| Chainalysis | *not present in baseline* | Planned by WS3 (`providers/chainalysis.py`), gated on `CHAINALYSIS_API_KEY` |
| CipherTrace | *not present in baseline* | Planned by WS3 (`providers/ciphertrace.py`), gated on `CIPHERTRACE_API_KEY` |

## Env vars (from `.env.example` / `core/config.py`)

`ALCHEMY_API_KEY`, `INFURA_API_KEY`, `INFURA_API_SECRET`, `ETHEREUM_RPC_URL`, `POLYGON_RPC_URL`,
`CHAINALYSIS_API_KEY`, `CIPHERTRACE_API_KEY`, `OFAC_SDN_LIST_URL`. All are `Optional[str] = None` in `Settings` except
`OFAC_SDN_LIST_URL`, which has a live default URL. None are validated as *required* at startup — see
`docs/KNOWN_LIMITATIONS.md` for the "silently degraded" behavior this produces when unset.

## Chain-name mapping

`services/wallet_analysis.py::WalletAnalysisService._get_chain_id` hardcodes a human-readable-name → chain-id map
(`"Ethereum": 1, "Polygon": 137, "BSC": 56, "Arbitrum": 42161, "Optimism": 10, "Base": 8453`) even though only
Ethereum and Polygon have registered providers in the baseline — BSC/Arbitrum/Optimism/Base will resolve a chain id
but then fail to find a provider.
