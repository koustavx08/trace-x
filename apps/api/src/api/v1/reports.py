from uuid import UUID
from typing import Any, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from src.core import get_session, NotFoundError
from src.models import Report
from src.schemas import ReportCreate, ReportResponse, PaginatedResponse
from src.workers.tasks import report_generation_task
from src.workers.main import celery_app

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportGenerateRequest(BaseModel):
    case_id: UUID
    investigation_run_id: Optional[UUID] = None
    title: Optional[str] = Field(None, max_length=255)
    template: str = Field("technical_findings")
    format: str = Field("pdf", pattern="^(pdf|json|html)$")


class ReportGenerateResponse(BaseModel):
    task_id: str
    status: str = "queued"


class ReportTaskStatusResponse(BaseModel):
    task_id: str
    state: str
    ready: bool
    result: Optional[Any] = None
    error: Optional[str] = None


@router.post("/generate", response_model=ReportGenerateResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_report(request: ReportGenerateRequest) -> ReportGenerateResponse:
    """Kick off report generation (build content from case/investigation
    data + render to PDF/JSON/HTML) as a background Celery task instead of
    doing it synchronously in the request path. Poll
    `GET /reports/tasks/{task_id}` for completion; the task persists the
    resulting `Report` row itself (see `report_generation_task`)."""
    task = report_generation_task.delay(
        str(request.case_id),
        str(request.investigation_run_id) if request.investigation_run_id else None,
        request.title,
        request.template,
        request.format,
        "system",
    )
    return ReportGenerateResponse(task_id=task.id, status="queued")


@router.get("/tasks/{task_id}", response_model=ReportTaskStatusResponse)
async def get_report_task_status(task_id: str) -> ReportTaskStatusResponse:
    async_result = celery_app.AsyncResult(task_id)

    error = None
    result = None
    if async_result.ready():
        if async_result.successful():
            result = async_result.result
        elif async_result.failed():
            error = str(async_result.result)

    return ReportTaskStatusResponse(
        task_id=task_id,
        state=async_result.state,
        ready=async_result.ready(),
        result=result,
        error=error,
    )


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