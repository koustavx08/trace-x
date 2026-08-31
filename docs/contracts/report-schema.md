# Report Generation Schema

> **Status:** Baseline reference (pre-parallel-merge). Derived from `apps/api/src/models/__init__.py::Report`,
> `apps/api/src/schemas/__init__.py` (`ReportBase`/`ReportCreate`/`ReportResponse`), `apps/api/src/api/v1/risk.py`,
> `apps/api/src/api/v1/reports.py`, and `apps/api/src/workers/tasks.py::report_generation_task`.

## Baseline blocker: `src/reports` module does not exist

Both `apps/api/src/api/v1/risk.py` (`from src.reports import report_generator, ReportFormat, ReportTemplate`) and
`apps/api/src/workers/tasks.py` (`from src.reports import report_generator, ReportFormat, ReportTemplate`) import a
`src/reports` package that **is not present anywhere in the baseline tree** (confirmed via `find src -iname
"*report*"` returning only `src/api/v1/reports.py`). As written, importing either module raises `ModuleNotFoundError`,
which — because `main.py` presumably wires up the `risk` router at import time — would prevent the FastAPI app from
starting at all until this module exists.

This matches WS3's task list exactly (`apps/api/src/reports/generator.py` is listed as a **new** file WS3 owns), so it
is expected to be filled in by that workstream. Documented here as ground truth for what the *rest* of the code
already assumes `report_generator` provides, inferred from call sites:

```python
# Expected surface, inferred from call sites in risk.py / tasks.py:
class ReportFormat(str, Enum):
    ...  # JSON used as ReportFormat.JSON in risk.py; PDF implied by "pdf" being a valid Report.format value

class ReportTemplate(str, Enum):
    TECHNICAL_FINDINGS = ...  # used as the default template

report_generator.generate_report(
    case_id: str,
    investigation_run_id: str | None,
    title: str | None,
    template: ReportTemplate,
    format: ReportFormat,
    generated_by: str,
) -> Report  # object with: .title, .sections (list of {.title, .content, .order}), .format, .file_content, .generated_at
```

## `Report` DB model

See `domain-model.md` for the full column list. Key fields: `findings` (JSON), `risk_assessment` (JSON),
`graph_snapshot` (JSON?), `format` (`pdf|json|html`, validated by regex at the schema layer), `file_path` (nullable —
baseline never actually writes report content to disk/object storage; see below).

## Two separate report-related surfaces

1. **`src/api/v1/reports.py`** (`/reports` prefix) — plain CRUD directly against the `Report` table
   (`POST/GET /reports`, `GET /reports/{id}`). The caller supplies `findings`/`risk_assessment`/`summary` themselves;
   no generation logic involved.
2. **`src/api/v1/risk.py`** (`/risk/reports/*`) — the actual *generation* pipeline:
   - `POST /risk/reports/generate` — calls `report_generator.generate_report(...)` (blocked on the missing module
     above), then persists a `Report` row summarizing the generated sections.
   - `GET /risk/reports/{id}/download` — **hardcoded stub**: returns a fixed byte string
     `b"Report content would be here - stored in object storage in production"` regardless of the report's actual
     `format`, with only the `Content-Type`/`Content-Disposition` headers varying by `report.format`. This means a
     "PDF" download today would not start with `%PDF-` magic bytes — it is HTML-adjacent placeholder text relabeled
     with a PDF content-type. WS3's task list explicitly targets this: real PDF rendering (`weasyprint` or
     `reportlab`) in `reports/generator.py`, with a stated verification criterion of "a PDF report response starts
     with `%PDF-` magic bytes." Re-verify `download_report` was updated to actually stream `report.file_content` /
     read from `file_path` once WS3 lands — the version read for this doc still returns the hardcoded placeholder.

## Celery task: `report_generation_task` (`workers/tasks.py`)

Defined and ready to `.delay()`, same missing-module blocker as above. On success, persists a `Report` row and
returns `{status, report_id, file_size}`. `api/v1/reports.py` and `api/v1/risk.py` do not currently call
`report_generation_task.delay(...)` anywhere in the baseline tree — report generation runs inline
(`await report_generator.generate_report(...)`) from the `POST /risk/reports/generate` endpoint, not as a background
job. WS3's task list calls for wiring this through Celery so the endpoint returns a task id instead of blocking.

## Frontend consumption

`apps/web/src/lib/api.ts::reportsApi` covers the plain CRUD surface (`/reports`); `riskApi.generateReport` /
`riskApi.downloadReport` cover the generation pipeline. Both are already typed client-side even though the backend
generation module doesn't exist yet in baseline — the frontend contract was written ahead of the backend
implementation.
