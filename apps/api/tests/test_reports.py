"""
Tests for report generation and delivery.

There is no real `apps/api/src/reports/generator.py` in this worktree at
all -- it's caught by a broad `reports/` rule in the repo's root
`.gitignore`, so it never got committed even though `src/api/v1/risk.py`
imports `report_generator`/`ReportFormat`/`ReportTemplate` from it. WS3
owns creating that module for real (JSON/HTML native, PDF via
weasyprint/reportlab). `tests/conftest.py` installs a minimal in-memory
stand-in (see the "WS4 test-only shim" block there) purely so the app can
import at all in a fresh checkout; it does NOT implement real
report/PDF rendering.

Given that, this file tests two things:

1. `src/api/v1/reports.py` -- the real, already-implemented Report CRUD
   endpoints (create/list/get), which store report metadata as JSON rows
   in Postgres. These need a real `tracex_test` database and skip cleanly
   if one isn't reachable.
2. `POST /risk/reports/generate` and `GET /risk/reports/{id}/download` in
   `src/api/v1/risk.py`, exercised against the conftest shim. The magic
   byte assertions for PDF are marked `xfail` since PDF generation is
   entirely a stub today (the download endpoint literally returns a fixed
   placeholder byte string regardless of format) -- they're written to
   *start passing* once WS3's real PDF renderer lands, per the plan's own
   verification bar ("a PDF report response starts with `%PDF-` magic
   bytes").
"""

from uuid import uuid4

import pytest
from fixtures_db import api_client, db_session  # noqa: F401


async def _create_case(db_session):
    from src.models import Case, CaseStatus, CrimeType

    case = Case(
        case_number=f"TRX-TEST-{uuid4().hex[:6]}",
        title="Report Test Case",
        crime_type=CrimeType.FRAUD,
        description="test case for report generation",
        status=CaseStatus.OPEN,
    )
    db_session.add(case)
    await db_session.flush()
    await db_session.commit()
    return case


async def _create_user(db_session):
    """A real `users` row to use as `generated_by`.

    `reports.generated_by` is a FK to `users.id`, so passing a throwaway
    `uuid4()` makes the INSERT fail with a ForeignKeyViolationError (surfacing
    as a 500) rather than exercising the report-creation path under test.
    """
    from src.models import User, UserRole

    user = User(
        email=f"reporter-{uuid4().hex[:8]}@tracex.test",
        full_name="Report Author",
        hashed_password="not-a-real-hash",
        role=UserRole.ANALYST,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


# ---------------------------------------------------------------------------
# src/api/v1/reports.py -- Report CRUD (real, DB-backed)
# ---------------------------------------------------------------------------


class TestReportCRUD:
    async def test_create_json_report(self, api_client, db_session):
        case = await _create_case(db_session)
        user = await _create_user(db_session)

        response = await api_client.post(
            "/api/v1/reports",
            params={"case_id": str(case.id), "generated_by": str(user.id)},
            json={
                "title": "Investigation Summary",
                "summary": "A short summary.",
                "findings": {"key": "value"},
                "risk_assessment": {"overall_score": 42.0},
                "format": "json",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["format"] == "json"
        assert body["title"] == "Investigation Summary"

    async def test_create_html_report(self, api_client, db_session):
        case = await _create_case(db_session)
        user = await _create_user(db_session)

        response = await api_client.post(
            "/api/v1/reports",
            params={"case_id": str(case.id), "generated_by": str(user.id)},
            json={
                "title": "HTML Report",
                "summary": "Summary text",
                "findings": {},
                "risk_assessment": {},
                "format": "html",
            },
        )
        assert response.status_code == 201
        assert response.json()["format"] == "html"

    async def test_create_report_rejects_invalid_format(self, api_client, db_session):
        case = await _create_case(db_session)

        response = await api_client.post(
            "/api/v1/reports",
            params={"case_id": str(case.id), "generated_by": str(uuid4())},
            json={
                "title": "Bad Format",
                "summary": "x",
                "findings": {},
                "risk_assessment": {},
                "format": "docx",
            },
        )
        assert response.status_code == 422

    async def test_create_report_unknown_case_returns_404(self, api_client):
        response = await api_client.post(
            "/api/v1/reports",
            params={"case_id": str(uuid4()), "generated_by": str(uuid4())},
            json={
                "title": "Orphan Report",
                "summary": "x",
                "findings": {},
                "risk_assessment": {},
            },
        )
        assert response.status_code == 404

    async def test_list_reports_filtered_by_case(self, api_client, db_session):
        case = await _create_case(db_session)
        user = await _create_user(db_session)
        for i in range(3):
            await api_client.post(
                "/api/v1/reports",
                params={"case_id": str(case.id), "generated_by": str(user.id)},
                json={
                    "title": f"Report {i}",
                    "summary": "x",
                    "findings": {},
                    "risk_assessment": {},
                },
            )

        response = await api_client.get("/api/v1/reports", params={"case_id": str(case.id)})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3

    async def test_get_report_by_id(self, api_client, db_session):
        case = await _create_case(db_session)
        user = await _create_user(db_session)
        create_resp = await api_client.post(
            "/api/v1/reports",
            params={"case_id": str(case.id), "generated_by": str(user.id)},
            json={
                "title": "Fetchable Report",
                "summary": "x",
                "findings": {},
                "risk_assessment": {},
            },
        )
        report_id = create_resp.json()["id"]

        response = await api_client.get(f"/api/v1/reports/{report_id}")
        assert response.status_code == 200
        assert response.json()["id"] == report_id

    async def test_get_report_not_found(self, api_client):
        response = await api_client.get(f"/api/v1/reports/{uuid4()}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /risk/reports/generate + /risk/reports/{id}/download
# ---------------------------------------------------------------------------


class TestRiskReportGeneration:
    async def test_generate_report_succeeds(self, api_client, db_session):
        """The success path the previous version of this test said to switch to.

        `src/api/v1/risk.py` now imports `Report` (the old NameError is gone)
        and hands its request session to `report_generator.generate_report`,
        so the generator reads the case from the same database/transaction the
        test created it in instead of opening its own.
        """
        case = await _create_case(db_session)
        user = await _create_user(db_session)

        response = await api_client.post(
            "/api/v1/risk/reports/generate",
            json={
                "case_id": str(case.id),
                "format": "json",
                "generated_by": str(user.id),
            },
        )
        assert response.status_code == 201
        assert response.json()["report_id"]

    @pytest.mark.xfail(
        reason=(
            "Blocked on the missing `Report` import bug in "
            "src/api/v1/risk.py (see "
            "test_generate_report_currently_500s_due_to_missing_report_import). "
            "Expected to start passing once that's fixed and WS3's real "
            "PDF renderer lands."
        ),
        strict=False,
    )
    async def test_download_pdf_report_has_pdf_magic_bytes(self, api_client, db_session):
        case = await _create_case(db_session)
        user = await _create_user(db_session)
        generate_resp = await api_client.post(
            "/api/v1/risk/reports/generate",
            json={
                "case_id": str(case.id),
                "format": "pdf",
                "generated_by": str(user.id),
            },
        )
        report_id = generate_resp.json()["report_id"]

        download_resp = await api_client.get(f"/api/v1/risk/reports/{report_id}/download")
        assert download_resp.content.startswith(b"%PDF-")

    async def test_generate_report_unknown_case_returns_404(self, api_client):
        response = await api_client.post(
            "/api/v1/risk/reports/generate",
            json={
                "case_id": str(uuid4()),
                "format": "json",
                "generated_by": str(uuid4()),
            },
        )
        assert response.status_code == 404
