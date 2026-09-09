from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import NotFoundError, get_session
from src.models import InvestigationRun, InvestigationStatus
from src.schemas import (
    InvestigationRunCreate,
    InvestigationRunResponse,
    InvestigationRunUpdate,
    PaginatedResponse,
)

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.post("", response_model=InvestigationRunResponse, status_code=status.HTTP_201_CREATED)
async def create_investigation(
    investigation_data: InvestigationRunCreate,
    case_id: UUID = Query(..., description="Case ID"),
    wallet_id: UUID = Query(..., description="Wallet ID to investigate"),
    session: AsyncSession = Depends(get_session),
) -> InvestigationRunResponse:
    from src.models import Case, Wallet

    case_result = await session.execute(select(Case).where(Case.id == case_id))
    case = case_result.scalar_one_or_none()
    if not case:
        raise NotFoundError("Case", str(case_id))

    wallet_result = await session.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = wallet_result.scalar_one_or_none()
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    investigation = InvestigationRun(
        case_id=case_id,
        wallet_id=wallet_id,
        status=InvestigationStatus.PENDING,
        config=investigation_data.config,
    )
    session.add(investigation)
    await session.flush()
    await session.refresh(investigation)
    return InvestigationRunResponse.model_validate(investigation)


@router.get("", response_model=PaginatedResponse)
async def list_investigations(
    case_id: UUID | None = None,
    wallet_id: UUID | None = None,
    status: str | None = Query(None, description="Status or comma-separated list of statuses"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse:
    query = select(InvestigationRun).order_by(InvestigationRun.created_at.desc())

    if case_id:
        query = query.where(InvestigationRun.case_id == case_id)
    if wallet_id:
        query = query.where(InvestigationRun.wallet_id == wallet_id)
    if status:
        status_values = [s.strip().lower() for s in status.split(",") if s.strip()]
        valid_statuses = [
            InvestigationStatus(s)
            for s in status_values
            if s in InvestigationStatus._value2member_map_
        ]
        if len(valid_statuses) == 1:
            query = query.where(InvestigationRun.status == valid_statuses[0])
        elif len(valid_statuses) > 1:
            query = query.where(InvestigationRun.status.in_(valid_statuses))

    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    investigations = result.scalars().all()

    return PaginatedResponse(
        items=[InvestigationRunResponse.model_validate(i) for i in investigations],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{investigation_id}", response_model=InvestigationRunResponse)
async def get_investigation(
    investigation_id: UUID, session: AsyncSession = Depends(get_session)
) -> InvestigationRunResponse:
    result = await session.execute(
        select(InvestigationRun).where(InvestigationRun.id == investigation_id)
    )
    investigation = result.scalar_one_or_none()
    if not investigation:
        raise NotFoundError("Investigation", str(investigation_id))
    return InvestigationRunResponse.model_validate(investigation)


@router.patch("/{investigation_id}", response_model=InvestigationRunResponse)
async def update_investigation(
    investigation_id: UUID,
    investigation_data: InvestigationRunUpdate,
    session: AsyncSession = Depends(get_session),
) -> InvestigationRunResponse:
    result = await session.execute(
        select(InvestigationRun).where(InvestigationRun.id == investigation_id)
    )
    investigation = result.scalar_one_or_none()
    if not investigation:
        raise NotFoundError("Investigation", str(investigation_id))

    update_data = investigation_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(investigation, field, value)

    await session.flush()
    await session.refresh(investigation)
    return InvestigationRunResponse.model_validate(investigation)
