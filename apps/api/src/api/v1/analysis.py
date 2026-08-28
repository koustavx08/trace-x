from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from src.core import get_session, NotFoundError, ValidationError
from src.models import Wallet, Case
from src.schemas import WalletCreate, WalletResponse, InvestigationRunResponse
from src.services import wallet_analysis_service

router = APIRouter(prefix="/analysis", tags=["analysis"])


class WalletAnalyzeRequest(BaseModel):
    address: str = Field(..., min_length=42, max_length=42)
    chain_id: Optional[int] = Field(None, ge=1)
    label: Optional[str] = Field(None, max_length=100)
    trace_depth: int = Field(5, ge=1, le=10)
    max_transactions: int = Field(1000, ge=100, le=10000)


class WalletAnalyzeResponse(BaseModel):
    wallet: WalletResponse
    investigation: InvestigationRunResponse


class TraceRequest(BaseModel):
    max_hops: int = Field(5, ge=1, le=10)
    min_value_eth: float = Field(0.001, ge=0)


@router.post("/wallets/validate", response_model=dict)
async def validate_wallet_address(
    address: str = Query(..., min_length=42, max_length=42),
    chain_id: Optional[int] = Query(None, ge=1),
):
    from src.core.validation import is_valid_evm_address, to_checksum, get_chain_info, detect_chain_from_address

    if not is_valid_evm_address(address):
        return {"valid": False, "error": "Invalid EVM address format"}

    checksum_addr = to_checksum(address)
    detected_chain = detect_chain_from_address(address)

    if chain_id:
        chain_info = get_chain_info(chain_id)
        if not chain_info:
            return {"valid": False, "error": f"Unsupported chain ID: {chain_id}"}
        target_chain = chain_id
    else:
        target_chain = detected_chain or 1
        chain_info = get_chain_info(target_chain)

    return {
        "valid": True,
        "address": checksum_addr,
        "original_address": address,
        "chain_id": target_chain,
        "chain_name": chain_info["name"],
        "chain_symbol": chain_info["symbol"],
        "explorer_url": chain_info["explorer"],
        "detected_chain": detected_chain,
    }


@router.post("/cases/{case_id}/wallets/analyze", response_model=WalletAnalyzeResponse)
async def analyze_wallet_in_case(
    case_id: UUID,
    request: WalletAnalyzeRequest,
    session: AsyncSession = Depends(get_session),
):
    case = await session.get(Case, case_id)
    if not case:
        raise NotFoundError("Case", str(case_id))

    wallet = await wallet_analysis_service.validate_and_create_wallet(
        case_id=case_id,
        address=request.address,
        chain_id=request.chain_id,
        label=request.label,
    )

    investigation = await wallet_analysis_service.analyze_wallet(
        wallet_id=wallet.id,
        trace_depth=request.trace_depth,
        max_transactions=request.max_transactions,
    )

    return WalletAnalyzeResponse(wallet=wallet, investigation=investigation)


@router.post("/wallets/{wallet_id}/trace", response_model=dict)
async def trace_fund_flow(
    wallet_id: UUID,
    request: TraceRequest,
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    result = await wallet_analysis_service.trace_fund_flow(
        wallet_id=wallet_id,
        max_hops=request.max_hops,
        min_value_eth=request.min_value_eth,
    )

    return result


@router.get("/wallets/{wallet_id}/transactions")
async def get_wallet_transactions(
    wallet_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    from sqlalchemy import select, func
    from src.models import Transaction

    query = select(Transaction).where(Transaction.wallet_id == wallet_id).order_by(Transaction.block_number.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    transactions = result.scalars().all()

    return {
        "items": [
            {
                "tx_hash": tx.tx_hash,
                "block_number": tx.block_number,
                "timestamp": tx.timestamp.isoformat(),
                "from_address": tx.from_address,
                "to_address": tx.to_address,
                "value": tx.value,
                "value_usd": tx.value_usd,
                "token_address": tx.token_address,
                "token_symbol": tx.token_symbol,
                "method": tx.method,
                "is_suspicious": tx.is_suspicious,
            }
            for tx in transactions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/chains")
async def list_supported_chains():
    from src.core.validation import get_supported_chains

    chains = get_supported_chains()
    return {"chains": [{"chain_id": k, **v} for k, v in chains.items()]}