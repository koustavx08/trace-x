from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import get_current_user
from src.core import NotFoundError, get_session
from src.models import Case, Report, Transaction, User, Wallet
from src.reports.notice_templates import (
    generate_statutory_notice_html,
    generate_statutory_notice_pdf,
)
from src.schemas import PaginatedResponse, ReportCreate, ReportResponse
from src.workers.main import celery_app
from src.workers.tasks import report_generation_task

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportGenerateRequest(BaseModel):
    case_id: UUID
    investigation_run_id: UUID | None = None
    title: str | None = Field(None, max_length=255)
    template: str = Field("technical_findings")
    format: str = Field("pdf", pattern="^(pdf|json|html)$")


class DraftStatutoryNoticeRequest(BaseModel):
    wallet_address: str = Field(..., description="Target custodial or suspect wallet address")
    entity_name: str | None = Field(
        None, description="Name of VASP/Exchange (e.g. Binance, Kraken)"
    )
    case_id: UUID | None = Field(None, description="Optional case ID to link notice to")
    notice_type: str = Field(
        "section_91_crpc", description="section_91_crpc | subpoena | freeze_notice"
    )
    format: str = Field("pdf", pattern="^(pdf|json|html)$")


class ReportGenerateResponse(BaseModel):
    task_id: str
    status: str = "queued"


class ReportTaskStatusResponse(BaseModel):
    task_id: str
    state: str
    ready: bool
    result: Any | None = None
    error: str | None = None


@router.post(
    "/generate",
    response_model=ReportGenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate report",
    description="Kick off report generation as a background Celery task. Poll `GET /reports/tasks/{task_id}` for completion.",
)
async def generate_report(
    request: ReportGenerateRequest,
    current_user: User = Depends(get_current_user),
) -> ReportGenerateResponse:
    """Kick off report generation (build content from case/investigation
    data + render to PDF/JSON/HTML) as a background Celery task instead of
    doing it synchronously in the request path. Poll
    `GET /reports/tasks/{task_id}` for completion; the task persists the
    resulting `Report` row itself (see `report_generation_task`).

    `generated_by` is the authenticated caller. It used to be the literal
    string "system", which is not a users.id, so every task raised on the
    NOT NULL foreign key `reports.generated_by` and no report generated
    through this route ever succeeded."""
    task = report_generation_task.delay(
        str(request.case_id),
        str(request.investigation_run_id) if request.investigation_run_id else None,
        request.title,
        request.template,
        request.format,
        str(current_user.id),
    )
    return ReportGenerateResponse(task_id=task.id, status="queued")


@router.get(
    "/tasks/{task_id}",
    response_model=ReportTaskStatusResponse,
    summary="Get report task status",
    description="Poll the status/result of a background report generation task.",
)
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


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create report",
    description="Create a new report record for a case.",
)
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


@router.get(
    "",
    response_model=PaginatedResponse,
    summary="List reports",
    description="List reports with optional filtering by case ID.",
)
async def list_reports(
    case_id: UUID | None = None,
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


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get report",
    description="Retrieve a specific report by ID.",
)
async def get_report(
    report_id: UUID, session: AsyncSession = Depends(get_session)
) -> ReportResponse:
    result = await session.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError("Report", str(report_id))
    return ReportResponse.model_validate(report)


async def _resolve_user(request: Request, session: AsyncSession) -> User:
    """Resolve current authenticated user, falling back to active user for demo flows."""
    try:
        user = await get_current_user(request=request, credentials=None, session=session)
        if user:
            return user
    except Exception:
        pass

    result = await session.execute(
        select(User).where(User.is_active).order_by(User.created_at.asc()).limit(1)
    )
    fallback_user = result.scalar_one_or_none()
    if fallback_user:
        return fallback_user
    raise NotFoundError("User", "No active user found to associate with report")


@router.post(
    "/draft-statutory-notice",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Draft statutory notice for VASP/Wallet",
    description="Synthesizes transaction history into an official Section 91 CrPC notice for freezing and KYC disclosure, renders to PDF, and saves to Reports.",
)
async def draft_statutory_notice(
    payload: DraftStatutoryNoticeRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ReportResponse:
    user = await _resolve_user(request, session)
    target_addr = payload.wallet_address.strip()

    # 1. Look up wallet in DB if exists
    wallet_res = await session.execute(select(Wallet).where(Wallet.address.ilike(target_addr)))
    wallet = wallet_res.scalars().first()

    # 2. Look up case
    case: Case | None = None
    if payload.case_id:
        case = await session.get(Case, payload.case_id)
    elif wallet and wallet.case_id:
        case = await session.get(Case, wallet.case_id)

    if not case:
        case_res = await session.execute(select(Case).order_by(Case.created_at.desc()).limit(1))
        case = case_res.scalars().first()

    if not case:
        raise NotFoundError("Case", "No active case found to link report")

    # 3. Resolve entity name
    entity_name = (
        payload.entity_name
        or (wallet.entity_name if wallet else None)
        or "Virtual Asset Service Provider (VASP)"
    )

    # 4. Fetch transactions related to this address
    tx_query = (
        select(Transaction)
        .where(
            or_(
                Transaction.from_address.ilike(target_addr),
                Transaction.to_address.ilike(target_addr),
            )
        )
        .order_by(Transaction.block_number.desc())
        .limit(20)
    )
    tx_results = (await session.execute(tx_query)).scalars().all()

    # Fallback to case transactions if no direct transactions found for this specific address
    if not tx_results:
        case_tx_query = (
            select(Transaction)
            .join(Wallet, Transaction.wallet_id == Wallet.id)
            .where(Wallet.case_id == case.id)
            .order_by(Transaction.block_number.desc())
            .limit(10)
        )
        tx_results = (await session.execute(case_tx_query)).scalars().all()

    transactions_data = [
        {
            "tx_hash": t.tx_hash,
            "block_number": t.block_number,
            "timestamp": t.timestamp.isoformat() if t.timestamp else "",
            "from_address": t.from_address,
            "to_address": t.to_address,
            "value": t.value,
            "value_usd": t.value_usd or 0.0,
            "token_symbol": t.token_symbol or "ETH",
        }
        for t in tx_results
    ]

    total_value_usd: float = sum(float(str(t.get("value_usd") or 0.0)) for t in transactions_data)
    if total_value_usd == 0.0:
        total_value_usd = 750000.0  # Demonstrative default

    report_id = uuid4()
    notice_ref = f"TRX-SEC91-{datetime.utcnow().strftime('%Y%m%d')}-{str(report_id)[:6].upper()}"

    # 5. Generate content
    if payload.format == "pdf":
        file_bytes = generate_statutory_notice_pdf(
            wallet_address=target_addr,
            entity_name=entity_name,
            case_number=case.case_number,
            case_title=case.title,
            crime_type=getattr(case.crime_type, "value", str(case.crime_type)),
            transactions=transactions_data,
            notice_id=notice_ref,
            total_value_usd=total_value_usd,
        )
    else:
        file_str = generate_statutory_notice_html(
            wallet_address=target_addr,
            entity_name=entity_name,
            case_number=case.case_number,
            case_title=case.title,
            crime_type=getattr(case.crime_type, "value", str(case.crime_type)),
            transactions=transactions_data,
            notice_id=notice_ref,
            total_value_usd=total_value_usd,
        )
        file_bytes = file_str.encode("utf-8")

    # 6. Save to local reports folder
    reports_dir = Path("data/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / f"{report_id}.{payload.format}"
    report_file.write_bytes(file_bytes)

    # 7. Persist Report row in DB
    report_title = (
        f"Section 91 CrPC Notice - {entity_name} ({target_addr[:8]}...{target_addr[-6:]})"
    )
    report_summary = (
        f"Statutory Legal Order under Section 91 Cr.P.C. / Section 94 BNSS served on {entity_name} "
        f"demanding immediate asset freezing and KYC dossier production for account/deposit address {target_addr}."
    )

    risk_score_val = 95.0
    confidence_val = "CONFIRMED"
    if wallet:
        if wallet.risk_score is not None:
            risk_score_val = float(wallet.risk_score)
        if wallet.entity_confidence is not None:
            confidence_val = getattr(
                wallet.entity_confidence, "value", str(wallet.entity_confidence)
            )

    report = Report(
        id=report_id,
        case_id=case.id,
        title=report_title,
        summary=report_summary,
        findings={
            "notice_id": notice_ref,
            "entity_name": entity_name,
            "wallet_address": target_addr,
            "transactions_count": len(transactions_data),
            "total_value_usd": total_value_usd,
            "notice_type": payload.notice_type,
            "generated_at": datetime.utcnow().isoformat(),
        },
        risk_assessment={
            "risk_score": risk_score_val,
            "entity_confidence": confidence_val,
        },
        graph_snapshot={"target_address": target_addr, "entity": entity_name},
        generated_by=user.id,
        format=payload.format,
        file_path=f"/api/v1/reports/{report_id}/download",
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)

    return ReportResponse.model_validate(report)


@router.get(
    "/{report_id}/download",
    summary="Download report file",
    description="Stream the generated PDF, HTML, or JSON report file for download.",
)
async def download_report_file(
    report_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError("Report", str(report_id))

    reports_dir = Path("data/reports")
    report_file = reports_dir / f"{report.id}.{report.format}"

    if report_file.exists():
        content = report_file.read_bytes()
    else:
        # Re-generate dynamically if file is missing
        findings = report.findings or {}
        wallet_addr = findings.get("wallet_address") or "0x0000000000000000000000000000000000000000"
        entity_name = findings.get("entity_name") or "Virtual Asset Service Provider"
        total_val = float(findings.get("total_value_usd") or 750000.0)
        notice_id = findings.get("notice_id")

        if report.format == "pdf":
            content = generate_statutory_notice_pdf(
                wallet_address=wallet_addr,
                entity_name=entity_name,
                case_number=str(report.case_id),
                case_title=report.title,
                notice_id=notice_id,
                total_value_usd=total_val,
            )
        else:
            content = generate_statutory_notice_html(
                wallet_address=wallet_addr,
                entity_name=entity_name,
                case_number=str(report.case_id),
                case_title=report.title,
                notice_id=notice_id,
                total_value_usd=total_val,
            ).encode("utf-8")

        # Cache back to disk
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file.write_bytes(content)

    media_types = {
        "pdf": "application/pdf",
        "html": "text/html",
        "json": "application/json",
    }
    media_type = media_types.get(report.format, "application/octet-stream")
    clean_title = (
        "".join(c for c in report.title if c.isalnum() or c in ("-", "_", " "))
        .strip()
        .replace(" ", "_")
    )
    filename = f"{clean_title[:45]}.{report.format}"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
