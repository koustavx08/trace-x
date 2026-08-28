from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.core import get_session, NotFoundError
from src.models import Report
from src.schemas import ReportCreate, ReportResponse, PaginatedResponse

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    report_data: ReportCreate,
    case_id: UUID = Query(..., description="Case ID"),
    generated_by: UUID = Query(..., description="User ID who generated the report"),
    session: AsyncSession = Depends(get_session),
) -> ReportResponse:
    from src.models import Case, InvestigationRun

    case_result = await session.execute(select(Case).where(Case.id == case_id))
    case = case_result.scalar_one_or_none()
    if not case:
        raise NotFoundError("Case", str(case_id))

    if report_data.investigation_run_id:
        inv_result = await session.execute(
            select(InvestigationRun).where(InvestigationRun.id == report_data.investigation_run_id)
        )
        investigation = inv_result.scalar_one_or_none()
        if not investigation:
            raise NotFoundError("InvestigationRun", str(report_data.investigation_run_id))

    report = Report(
        case_id=case_id,
        investigation_run_id=report_data.investigation_run_id,
        title=report_data.title,
        summary=report_data.summary,
        findings=report_data.findings,
        risk_assessment=report_data.risk_assessment,
        graph_snapshot=report_data.graph_snapshot,
        generated_by=generated_by,
        format=report_data.format,
    )
    session.add(report)
    await session.flush()
    await session.refresh(report)
    return ReportResponse.model_validate(report)


@router.get("", response_model=PaginatedResponse)
async def list_reports(
    case_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse:
    query = select(Report).order_by(Report.created_at.desc())

    if case_id:
        query = query.where(Report.case_id == case_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await session.execute(query)
    reports = result.scalars().all()

    return PaginatedResponse(
        items=[ReportResponse.model_validate(r) for r in reports],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: UUID, session: AsyncSession = Depends(get_session)) -> ReportResponse:
    result = await session.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError("Report", str(report_id))
    return ReportResponse.model_validate(report)