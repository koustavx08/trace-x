import re
from typing import Optional, Tuple
from eth_utils import to_checksum_address, is_address
import structlog

logger = structlog.get_logger(__name__)

CHAIN_CONFIGS = {
    1: {"name": "Ethereum", "symbol": "ETH", "explorer": "https://etherscan.io", "rpc_env": "ETHEREUM_RPC_URL"},
    137: {"name": "Polygon", "symbol": "MATIC", "explorer": "https://polygonscan.com", "rpc_env": "POLYGON_RPC_URL"},
    56: {"name": "BSC", "symbol": "BNB", "explorer": "https://bscscan.com", "rpc_env": "BSC_RPC_URL"},
    42161: {"name": "Arbitrum", "symbol": "ETH", "explorer": "https://arbiscan.io", "rpc_env": "ARBITRUM_RPC_URL"},
    10: {"name": "Optimism", "symbol": "ETH", "explorer": "https://optimistic.etherscan.io", "rpc_env": "OPTIMISM_RPC_URL"},
    8453: {"name": "Base", "symbol": "ETH", "explorer": "https://basescan.org", "rpc_env": "BASE_RPC_URL"},
}

EVM_ADDRESS_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")


def is_valid_evm_address(address: str) -> bool:
    if not address or not isinstance(address, str):
        return False
    if not EVM_ADDRESS_REGEX.match(address):
        return False
    try:
        return is_address(address)
    except Exception:
        return False


def to_checksum(address: str) -> str:
    return to_checksum_address(address)


def detect_chain_from_address(address: str) -> Optional[int]:
    if not is_valid_evm_address(address):
        return None
    return 1


def get_supported_chains() -> dict:
    return CHAIN_CONFIGS.copy()


def get_chain_info(chain_id: int) -> Optional[dict]:
    return CHAIN_CONFIGS.get(chain_id)


def validate_and_normalize_address(address: str) -> Tuple[bool, Optional[str], Optional[str]]:
    if not is_valid_evm_address(address):
        return False, None, "Invalid EVM address format"

    try:
        checksum_addr = to_checksum_address(address)
        return True, checksum_addr, None
    except Exception as e:
        return False, None, f"Address normalization failed: {str(e)}"


def is_contract_address(w3, address: str) -> bool:
    try:
        code = w3.eth.get_code(to_checksum_address(address))
        return code != b"" and code != "0x"
    except Exception:
        return False