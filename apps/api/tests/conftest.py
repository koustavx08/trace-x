# conftest.py - pytest configuration with proper path setup
import os
import sys

# Add the src directory to the path BEFORE any other imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, "src")
sys.path.insert(0, src_path)

# Now we can import pytest and other modules
import asyncio
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.config import get_settings
from src.core.database import Base

# ---------------------------------------------------------------------------
# WS4 test-only shim: `apps/api/src/reports/` is matched by a broad `reports/`
# rule in the repo .gitignore, so it never got committed even though
# `src/api/v1/risk.py` does `from src.reports import report_generator,
# ReportFormat, ReportTemplate` at import time. In a fresh checkout/worktree
# (like this one) that makes the ENTIRE app fail to import -- including the
# pre-existing health-check tests below, which have nothing to do with
# reports. WS3 owns creating the real `apps/api/src/reports/generator.py`;
# until that lands, we register a minimal in-memory stand-in module here so
# the test suite (and CI) isn't permanently blocked. This is purely additive
# and does not touch any file outside apps/api/tests/**. Once the real
# module exists, this import succeeds and the whole block is a no-op.
try:
    import src.reports  # noqa: F401
except ModuleNotFoundError:
    import sys as _sys
    import types as _types
    from datetime import datetime as _datetime
    from enum import Enum as _Enum

    class ReportFormat(str, _Enum):
        JSON = "json"
        HTML = "html"
        PDF = "pdf"

    class ReportTemplate(str, _Enum):
        EXECUTIVE_SUMMARY = "executive_summary"
        TECHNICAL_FINDINGS = "technical_findings"
        EVIDENCE_PACKAGE = "evidence_package"
        LEGAL_BRIEF = "legal_brief"

    class _StubSection:
        def __init__(self, title, content, order):
            self.title = title
            self.content = content
            self.order = order

    class _StubReport:
        def __init__(self, title, sections, format, file_content, generated_at):
            self.title = title
            self.sections = sections
            self.format = format
            self.file_content = file_content
            self.generated_at = generated_at

    class _StubReportGenerator:
        """Minimal stand-in for the not-yet-committed real report generator.

        Produces JSON-ish bytes regardless of requested format -- this is a
        test-time shim, NOT a claim that PDF/HTML generation works. See
        tests/test_reports.py for tests that document this gap and are
        expected to need a fixup pass once WS3's real generator lands.
        """

        async def generate_report(
            self,
            case_id,
            investigation_run_id=None,
            title=None,
            template=ReportTemplate.TECHNICAL_FINDINGS,
            format=ReportFormat.JSON,
            generated_by="system",
        ):
            resolved_title = title or f"Investigation Report {case_id}"
            sections = [
                _StubSection("Executive Summary", "Stub content for tests.", 1),
                _StubSection("Wallet Analysis", "Stub content for tests.", 2),
            ]
            content = (
                '{{"case_id": "{}", "template": "{}", "stub": true}}'.format(
                    case_id, getattr(template, "value", template)
                )
            ).encode()
            return _StubReport(
                title=resolved_title,
                sections=sections,
                format=format,
                file_content=content,
                generated_at=_datetime.utcnow(),
            )

    _reports_pkg = _types.ModuleType("src.reports")
    _reports_pkg.ReportFormat = ReportFormat
    _reports_pkg.ReportTemplate = ReportTemplate
    _reports_pkg.report_generator = _StubReportGenerator()
    _sys.modules["src.reports"] = _reports_pkg
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL.replace("tracex", "tracex_test"),
        poolclass=NullPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()
