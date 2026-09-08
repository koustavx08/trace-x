from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics import attribution_engine, risk_scoring_engine
from src.core import NotFoundError, get_session
from src.graph.models import ConfidenceLevel, GraphTransaction, GraphWallet
from src.graph.queries import graph_queries
from src.models import Case, InvestigationRun, Report, Wallet
from src.reports import ReportFormat, ReportTemplate, report_generator

router = APIRouter(prefix="/risk", tags=["risk"])


class RiskAssessmentResponse(BaseModel):
    overall_score: float
    risk_level: str
    factors: list[dict]
    summary: str
    methodology: str
    assessed_at: str


class AttributionResponse(BaseModel):
    attributed: bool
    nearest_vasp: dict | None
    all_attributions: list[dict]
    summary: dict


class ReportGenerateRequest(BaseModel):
    case_id: UUID
    investigation_run_id: UUID | None = None
    title: str | None = None
    template: ReportTemplate = ReportTemplate.TECHNICAL_FINDINGS
    format: ReportFormat = ReportFormat.JSON
    # A real users.id, matching the FK on reports.generated_by and the
    # `generated_by: UUID` query param on POST /reports in api/v1/reports.py.
    # This used to be a free-form str defaulting to "analyst", which the
    # handler then fed to UUID() unless it equalled the *other* sentinel,
    # "system" -- so the endpoint raised ValueError ("badly formed hexadecimal
    # UUID string") on its own default input, and the "system" branch stored an
    # all-zeros UUID that no users row has, violating the foreign key.
    generated_by: UUID


class ReportGenerateResponse(BaseModel):
    report_id: UUID
    title: str
    format: str
    file_size: int
    generated_at: str


@router.post("/wallets/{wallet_id}/assess", response_model=RiskAssessmentResponse)
@router.get("/wallets/{wallet_id}/assess", response_model=RiskAssessmentResponse)
async def assess_wallet_risk(
    wallet_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    from sqlalchemy import select

    from src.models import Transaction

    result = await session.execute(select(Transaction).where(Transaction.wallet_id == wallet_id))
    transactions = result.scalars().all()

    graph_transactions = [
        GraphTransaction(
            tx_hash=tx.tx_hash,
            chain=wallet.chain,
            block_number=tx.block_number,
            timestamp=tx.timestamp,
            from_address=tx.from_address,
            to_address=tx.to_address,
            value=tx.value,
            value_usd=tx.value_usd,
            token_address=tx.token_address,
            token_symbol=tx.token_symbol,
            method=tx.method,
            is_suspicious=tx.is_suspicious,
            metadata=tx.transaction_metadata or {},
        )
        for tx in transactions
    ]
    graph_wallet = GraphWallet(
        address=wallet.address,
        chain=wallet.chain,
        label=wallet.label,
        risk_score=float(wallet.risk_score),
        first_seen=wallet.created_at,
        last_seen=wallet.updated_at,
        tx_count=len(graph_transactions),
        entity_name=wallet.entity_name,
        entity_confidence=ConfidenceLevel(wallet.entity_confidence)
        if wallet.entity_confidence
        else ConfidenceLevel.UNKNOWN,
    )

    graph_context = {}
    try:
        graph_context["mixer_interactions"] = await graph_queries.find_mixer_interactions(
            address=wallet.address,
            chain=wallet.chain,
            max_hops=4,
        )
        graph_context["peel_chains"] = await graph_queries.detect_peel_chains(
            chain=wallet.chain,
            min_hops=3,
        )
    except Exception:
        pass

    entity_data = None
    if wallet.entity_name:
        entity_data = {
            "entity_name": wallet.entity_name,
            "entity_type": wallet.entity_type,
            "confidence": wallet.entity_confidence,
        }

    assessment = await risk_scoring_engine.assess_wallet(
        wallet=graph_wallet,
        transactions=graph_transactions,
        entity_data=entity_data,
        graph_context=graph_context,
    )

    return RiskAssessmentResponse(**assessment.to_dict())


@router.get("/wallets/{wallet_id}/attribution", response_model=AttributionResponse)
async def get_wallet_attribution(
    wallet_id: UUID,
    max_hops: int = Query(6, ge=1, le=10),
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    result = await attribution_engine.get_attribution_summary(
        wallet_address=wallet.address,
        chain=wallet.chain,
    )

    return AttributionResponse(**result)


@router.post("/wallets/{wallet_id}/attribute", response_model=list[dict])
async def attribute_wallet(
    wallet_id: UUID,
    max_hops: int = Query(6, ge=1, le=10),
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    attributions = await attribution_engine.attribute_wallet(
        wallet_address=wallet.address,
        chain=wallet.chain,
        max_hops=max_hops,
    )

    return [a.to_dict() for a in attributions]


@router.post(
    "/reports/generate", response_model=ReportGenerateResponse, status_code=status.HTTP_201_CREATED
)
async def generate_report(
    request: ReportGenerateRequest,
    session: AsyncSession = Depends(get_session),
):
    case = await session.get(Case, request.case_id)
    if not case:
        raise NotFoundError("Case", str(request.case_id))

    if request.investigation_run_id:
        investigation = await session.get(InvestigationRun, request.investigation_run_id)
        if not investigation:
            raise NotFoundError("InvestigationRun", str(request.investigation_run_id))

    report = await report_generator.generate_report(
        case_id=str(request.case_id),
        investigation_run_id=str(request.investigation_run_id)
        if request.investigation_run_id
        else None,
        title=request.title or f"{case.title} - Investigation Report",
        template=request.template,
        format=request.format,
        generated_by=str(request.generated_by),
        # Reuse this request's session so the generator reads the case in the
        # same transaction that the Report row below is written in.
        session=session,
    )

    db_report = Report(
        case_id=request.case_id,
        investigation_run_id=request.investigation_run_id,
        title=report.title,
        summary=report.sections[0].content[:500] if report.sections else "",
        findings={
            "sections": [{"title": s.title, "order": s.order} for s in report.sections],
        },
        risk_assessment={},
        graph_snapshot={},
        generated_by=request.generated_by,
        format=request.format.value,
    )
    session.add(db_report)
    await session.flush()
    await session.refresh(db_report)

    return ReportGenerateResponse(
        report_id=db_report.id,
        title=report.title,
        format=report.format.value,
        file_size=len(report.file_content) if report.file_content else 0,
        generated_at=report.generated_at.isoformat(),
    )


@router.get("/reports/{report_id}/download")
async def download_report(
    report_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    report = await session.get(Report, report_id)
    if not report:
        raise NotFoundError("Report", str(report_id))

    from fastapi.responses import Response

    content = b"Report content would be here - stored in object storage in production"
    media_type = {
        "pdf": "application/pdf",
        "json": "application/json",
        "html": "text/html",
    }.get(report.format, "application/octet-stream")

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="report_{report.id}.{report.format}"'
        },
    )


@router.get("/cases/{case_id}/risk-summary")
async def get_case_risk_summary(
    case_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    case = await session.get(Case, case_id)
    if not case:
        raise NotFoundError("Case", str(case_id))

    from sqlalchemy import select

    result = await session.execute(select(Wallet).where(Wallet.case_id == case_id))
    wallets = result.scalars().all()

    if not wallets:
        return {
            "case_id": str(case_id),
            "case_number": case.case_number,
            "total_wallets": 0,
            "wallets": 0,
            "chains": [],
            "risk_distribution": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0,
            },
            "attribution": {
                "confirmed": 0,
                "probable": 0,
                "unattributed": 0,
            },
            "average_risk_score": 0.0,
            "top_risk_wallets": [],
            "message": "No wallets in case",
        }

    high_risk = len([w for w in wallets if float(w.risk_score or 0) >= 75])
    medium_risk = len([w for w in wallets if 40 <= float(w.risk_score or 0) < 75])
    low_risk = len([w for w in wallets if 20 <= float(w.risk_score or 0) < 40])
    info_risk = len([w for w in wallets if float(w.risk_score or 0) < 20])

    attributed = [
        w
        for w in wallets
        if w.entity_name and w.entity_confidence in ["CONFIRMED", "HIGH_CONFIDENCE"]
    ]
    probable = [w for w in wallets if w.entity_name and w.entity_confidence == "PROBABLE"]

    chains = list({w.chain for w in wallets})

    return {
        "case_id": str(case_id),
        "case_number": case.case_number,
        "total_wallets": len(wallets),
        "chains": chains,
        "risk_distribution": {
            "critical": high_risk,
            "high": 0,
            "medium": medium_risk,
            "low": low_risk,
            "info": info_risk,
        },
        "attribution": {
            "confirmed": len(attributed),
            "probable": len(probable),
            "unattributed": len(wallets) - len(attributed) - len(probable),
        },
        "average_risk_score": round(
            sum(float(w.risk_score or 0) for w in wallets) / len(wallets), 1
        )
        if wallets
        else 0,
        "top_risk_wallets": [
            {"address": w.address, "risk_score": w.risk_score, "label": w.label}
            for w in sorted(wallets, key=lambda x: float(x.risk_score or 0), reverse=True)[:5]
        ],
    }
