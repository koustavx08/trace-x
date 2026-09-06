from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import ConflictError, NotFoundError, get_session
from src.models import AttributionStatus, Case, Wallet
from src.schemas import PaginatedResponse, WalletCreate, WalletResponse, WalletUpdate

# WS3 note: this router only does CRUD on Wallet records; it contains no
# inline/synchronous heavy analysis calls (wallet analysis is triggered via
# `POST /analysis/cases/{case_id}/wallets/analyze` in api/v1/analysis.py,
# which now dispatches `wallet_analysis_task.delay(...)` to Celery instead of
# running inline). Nothing here needed to change for the Celery wiring.
router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.post("", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
async def create_wallet(
    wallet_data: WalletCreate,
    case_id: UUID = Query(..., description="Case ID to associate wallet with"),
    session: AsyncSession = Depends(get_session),
) -> WalletResponse:
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise NotFoundError("Case", str(case_id))

    # (case_id, address, chain) is uniquely indexed. Without this check the
    # INSERT raises an IntegrityError that nothing maps to a response, so a
    # duplicate surfaced as an unhandled 500 instead of a 409. Mirrors the
    # "Wallet already tracked in this case" guard in services/wallet_analysis.py.
    existing = await session.execute(
        select(Wallet).where(
            Wallet.case_id == case_id,
            Wallet.address == wallet_data.address,
            Wallet.chain == wallet_data.chain,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(
            "Wallet",
            f"Wallet {wallet_data.address} on {wallet_data.chain} is already tracked in this case.",
        )

    wallet = Wallet(
        case_id=case_id,
        address=wallet_data.address,
        chain=wallet_data.chain,
        label=wallet_data.label,
        attribution_status=wallet_data.attribution_status,
        risk_score=wallet_data.risk_score,
        entity_name=wallet_data.entity_name,
        entity_confidence=wallet_data.entity_confidence,
        first_seen_tx_hash=wallet_data.first_seen_tx_hash,
        wallet_metadata=wallet_data.metadata,
    )
    session.add(wallet)
    await session.flush()
    await session.refresh(wallet)
    return WalletResponse.model_validate(wallet)


@router.get("", response_model=PaginatedResponse)
async def list_wallets(
    case_id: UUID | None = None,
    chain: str | None = None,
    attribution_status: AttributionStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse:
    query = select(Wallet).order_by(Wallet.created_at.desc())

    if case_id:
        query = query.where(Wallet.case_id == case_id)
    if chain:
        query = query.where(Wallet.chain == chain)
    if attribution_status:
        query = query.where(Wallet.attribution_status == attribution_status)

    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    wallets = result.scalars().all()

    return PaginatedResponse(
        items=[WalletResponse.model_validate(w) for w in wallets],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{wallet_id}", response_model=WalletResponse)
async def get_wallet(
    wallet_id: UUID, session: AsyncSession = Depends(get_session)
) -> WalletResponse:
    result = await session.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))
    return WalletResponse.model_validate(wallet)


@router.patch("/{wallet_id}", response_model=WalletResponse)
async def update_wallet(
    wallet_id: UUID, wallet_data: WalletUpdate, session: AsyncSession = Depends(get_session)
) -> WalletResponse:
    result = await session.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    update_data = wallet_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(wallet, field, value)

    await session.flush()
    await session.refresh(wallet)
    return WalletResponse.model_validate(wallet)


@router.delete("/{wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wallet(wallet_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    result = await session.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    await session.delete(wallet)
