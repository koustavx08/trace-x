"""
Investigation report generation.

Builds a structured report from case/investigation/wallet data and renders
it to JSON, HTML, or PDF. This module did not previously exist even though
`src.workers.tasks` already imported from it (`report_generator`,
`ReportFormat`, `ReportTemplate`) — that import was broken until this file
was added.

PDF rendering uses `xhtml2pdf` (pure-Python, built on `reportlab`) to convert
the same HTML rendition produced by `_render_html` into a real PDF document,
rather than returning raw HTML bytes mislabeled as PDF.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import BytesIO
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import async_session_factory
from src.models import Case, InvestigationRun, Wallet

logger = structlog.get_logger(__name__)


class ReportFormat(str, Enum):
    PDF = "pdf"
    JSON = "json"
    HTML = "html"


class ReportTemplate(str, Enum):
    TECHNICAL_FINDINGS = "technical_findings"
    EXECUTIVE_SUMMARY = "executive_summary"
    LEGAL_BRIEF = "legal_brief"


@dataclass
class ReportSection:
    title: str
    content: str
    order: int = 0
    data: dict | None = None


@dataclass
class GeneratedReport:
    title: str
    case_id: str
    format: ReportFormat
    sections: list[ReportSection] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    file_content: bytes | None = None
    content_type: str = "application/json"


class ReportGenerator:
    """Builds report content from case/investigation data and renders it
    to the requested output format."""

    async def _load_sections(
        self,
        session: AsyncSession,
        case_id: str,
        investigation_run_id: str | None,
    ) -> list[ReportSection]:
        """Read the case/investigation/wallets and build the report sections."""
        case = await session.get(Case, UUID(case_id))
        if not case:
            raise ValueError(f"Case not found: {case_id}")

        investigation = None
        if investigation_run_id:
            investigation = await session.get(InvestigationRun, UUID(investigation_run_id))

        wallets_result = await session.execute(select(Wallet).where(Wallet.case_id == case.id))
        wallets = wallets_result.scalars().all()

        return self._build_sections(case, investigation, wallets)

    async def generate_report(
        self,
        case_id: str,
        title: str,
        investigation_run_id: str | None = None,
        template: str = ReportTemplate.TECHNICAL_FINDINGS.value,
        format: str = ReportFormat.PDF.value,
        generated_by: str = "system",
        session: AsyncSession | None = None,
    ) -> GeneratedReport:
        """Build a report for `case_id`.

        `session` lets a caller that already has one (an HTTP request, say)
        hand it in. Always opening a fresh `async_session_factory()` session
        meant the generator read the case in a *different* transaction from the
        endpoint that writes the resulting `Report` row -- and in tests it also
        bypassed the `get_session` dependency override, so it queried the real
        database instead of `tracex_test` and reported "Case not found" for a
        case the test had just created. Falls back to its own session when no
        caller supplies one (e.g. the Celery worker).
        """
        report_format = ReportFormat(format)

        if session is not None:
            sections = await self._load_sections(session, case_id, investigation_run_id)
        else:
            async with async_session_factory() as own_session:
                sections = await self._load_sections(own_session, case_id, investigation_run_id)

        report = GeneratedReport(
            title=title,
            case_id=case_id,
            format=report_format,
            sections=sections,
        )

        if report_format == ReportFormat.JSON:
            report.file_content = self._render_json(report)
            report.content_type = "application/json"
        elif report_format == ReportFormat.HTML:
            report.file_content = self._render_html(report)
            report.content_type = "text/html"
        elif report_format == ReportFormat.PDF:
            report.file_content = self._render_pdf(report)
            report.content_type = "application/pdf"
        else:
            raise ValueError(f"Unsupported report format: {format}")

        return report

    def _build_sections(self, case: Case, investigation, wallets) -> list[ReportSection]:
        sections: list[ReportSection] = []

        crime_type = getattr(case.crime_type, "value", case.crime_type)
        status = getattr(case.status, "value", case.status)

        sections.append(
            ReportSection(
                title="Case Overview",
                order=1,
                content=(
                    f"Case {case.case_number}: {case.title}\n\n"
                    f"Crime type: {crime_type}\n"
                    f"Status: {status}\n\n"
                    f"{case.description}"
                ),
            )
        )

        wallet_lines = []
        for w in wallets:
            attribution = getattr(w.attribution_status, "value", w.attribution_status)
            wallet_lines.append(
                f"- {w.address} ({w.chain}) - risk score {w.risk_score}, attribution: {attribution}"
            )
        sections.append(
            ReportSection(
                title="Tracked Wallets",
                order=2,
                content="\n".join(wallet_lines)
                if wallet_lines
                else "No wallets tracked in this case.",
            )
        )

        if investigation is not None:
            summary = investigation.result_summary or {}
            inv_status = getattr(investigation.status, "value", investigation.status)
            sections.append(
                ReportSection(
                    title="Investigation Findings",
                    order=3,
                    content=(
                        f"Investigation status: {inv_status}\n\n"
                        + json.dumps(summary, indent=2, default=str)
                    ),
                    data=summary,
                )
            )

        return sections

    def _render_json(self, report: GeneratedReport) -> bytes:
        payload = {
            "title": report.title,
            "case_id": report.case_id,
            "generated_at": report.generated_at.isoformat(),
            "sections": [
                {"title": s.title, "order": s.order, "content": s.content, "data": s.data}
                for s in sorted(report.sections, key=lambda s: s.order)
            ],
        }
        return json.dumps(payload, indent=2, default=str).encode("utf-8")

    def _render_html(self, report: GeneratedReport) -> bytes:
        sections_html = "".join(
            f"<section><h2>{self._escape(s.title)}</h2><pre>{self._escape(s.content)}</pre></section>"
            for s in sorted(report.sections, key=lambda s: s.order)
        )
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>{self._escape(report.title)}</title>
<style>
  body {{ font-family: Helvetica, Arial, sans-serif; margin: 2rem; color: #1a1a1a; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
  h2 {{ color: #333; margin-top: 2rem; }}
  pre {{ white-space: pre-wrap; background: #f5f5f5; padding: 1rem; border-radius: 4px; }}
  .meta {{ color: #666; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>{self._escape(report.title)}</h1>
<p class="meta">Case: {self._escape(report.case_id)} &middot; Generated: {report.generated_at.isoformat()}</p>
{sections_html}
</body>
</html>"""
        return html.encode("utf-8")

    @staticmethod
    def _escape(text: str) -> str:
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _render_pdf(self, report: GeneratedReport) -> bytes:
        """Render the report to a real PDF by converting the HTML rendition
        with xhtml2pdf (pure-Python, no system pango/cairo dependency)."""
        html_bytes = self._render_html(report)

        try:
            from xhtml2pdf import pisa
        except ImportError as e:
            logger.error("pdf_library_missing", detail=str(e))
            raise RuntimeError(
                "PDF rendering requires the 'xhtml2pdf' package; install project dependencies "
                "(pip install -e '.[dev]' or `pip install xhtml2pdf`)."
            ) from e

        output = BytesIO()
        result = pisa.CreatePDF(src=html_bytes.decode("utf-8"), dest=output, encoding="utf-8")

        if result.err:
            logger.error("pdf_render_failed", errors=result.err)
            raise RuntimeError(
                f"xhtml2pdf reported {result.err} error(s) rendering the report to PDF"
            )

        pdf_bytes = output.getvalue()
        if not pdf_bytes.startswith(b"%PDF-"):
            raise RuntimeError("PDF renderer did not produce a valid PDF payload")

        return pdf_bytes


report_generator = ReportGenerator()
