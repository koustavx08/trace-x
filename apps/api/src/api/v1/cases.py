import contextlib
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core import NotFoundError, get_session
from src.models import Case, CaseStatus, CrimeType
from src.schemas import (
    CaseCreate,
    CaseResponse,
    CaseUpdate,
    PaginatedResponse,
)

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    case_data: CaseCreate, session: AsyncSession = Depends(get_session)
) -> CaseResponse:
    import random
    from datetime import datetime

    case_number = f"TRX-{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(1000, 9999):04d}"

    case = Case(
        case_number=case_number,
        title=case_data.title,
        crime_type=case_data.crime_type,
        description=case_data.description,
        status=case_data.status,
        assigned_to=case_data.assigned_to,
        case_metadata=case_data.metadata,
    )
    session.add(case)
    await session.flush()
    await session.refresh(case)
    return CaseResponse.model_validate(case)


@router.get("", response_model=PaginatedResponse)
async def list_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    crime_type: CrimeType | None = None,
    assigned_to: UUID | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse:
    query = select(Case).order_by(Case.created_at.desc())

    if status:
        raw_statuses = [s.strip() for s in status.split(",") if s.strip()]
        valid_statuses = []
        for s in raw_statuses:
            # Unknown values are ignored rather than rejected: the filter is a
            # UI convenience, and a stale bookmark should not 422 the case list.
            with contextlib.suppress(ValueError):
                valid_statuses.append(CaseStatus(s))
        if len(valid_statuses) == 1:
            query = query.where(Case.status == valid_statuses[0])
        elif len(valid_statuses) > 1:
            query = query.where(Case.status.in_(valid_statuses))
    if crime_type:
        query = query.where(Case.crime_type == crime_type)
    if assigned_to:
        query = query.where(Case.assigned_to == assigned_to)
    if search:
        like = f"%{search}%"
        query = query.where(Case.case_number.ilike(like) | Case.title.ilike(like))

    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    cases = result.scalars().all()

    return PaginatedResponse(
        items=[CaseResponse.model_validate(c) for c in cases],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: UUID, session: AsyncSession = Depends(get_session)) -> CaseResponse:
    result = await session.execute(
        select(Case).options(selectinload(Case.wallets)).where(Case.id == case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise NotFoundError("Case", str(case_id))
    return CaseResponse.model_validate(case)


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: UUID, case_data: CaseUpdate, session: AsyncSession = Depends(get_session)
) -> CaseResponse:
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise NotFoundError("Case", str(case_id))

    update_data = case_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case, field, value)

    await session.flush()
    await session.refresh(case)
    return CaseResponse.model_validate(case)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(case_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise NotFoundError("Case", str(case_id))

    await session.delete(case)
