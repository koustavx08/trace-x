"""
Statutory electronic-evidence certificate generator for TRACE-X.

Under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023 (which replaced Section 65B
of the Indian Evidence Act, 1872) electronic records tendered in court are inadmissible
unless accompanied by a signed certificate identifying the record, the system that
produced it, and a means of verifying that the record was not altered after extraction.

This module turns the transaction rows, wallet rows and graph snapshots pulled by the
TRACE-X engine into exactly that certificate: a per-record SHA-256 digest, a Merkle root
and a hash chain over the whole record set, the environment metadata the court needs to
identify the source system, and the formal declaration with the Investigating Officer's
signature block.

Everything here is deterministic by design. The Investigating Officer must be able to
re-run the certification months later, in the witness box, over the same exhibit files
and obtain byte-identical hashes -- so no randomness, no wall-clock reads inside the
hashing path, and canonical (key-order independent) JSON serialisation.
"""

from __future__ import annotations

import hashlib
import html
import json
import platform
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)

# Version stamped into the certificate's system metadata. Courts ask which build of the
# software produced the exhibit; bump this when the certification format changes.
CERTIFICATE_FORMAT_VERSION = "1.0.0"

# sha256 of the empty byte string. Doubles as the Merkle root of an empty record set and
# as the genesis link of the hash chain, so both are defined for zero records instead of
# raising or returning an empty string that would read as "not computed".
EMPTY_HASH = hashlib.sha256(b"").hexdigest()


@dataclass(frozen=True)
class EvidenceRecord:
    """One extracted item of electronic evidence to be certified."""

    record_id: str
    record_type: str
    payload: dict[str, Any]
    source: str


@dataclass(frozen=True)
class EvidenceCertificate:
    """A Section 63 BSA / Section 65B IEA certificate over a set of evidence records."""

    certificate_id: str
    generated_at: datetime
    case_number: str
    investigating_officer: str
    record_count: int
    record_hashes: tuple[str, ...]
    merkle_root: str
    hash_chain: tuple[str, ...]
    chain_tip: str
    system_metadata: dict[str, Any]
    declaration: str


def _escape(val: Any) -> str:
    return html.escape(str(val if val is not None else ""))


def _iso_utc(value: datetime | date) -> str:
    """Serialise a date/datetime as ISO-8601 in UTC.

    Naive datetimes are treated as UTC rather than as local time: every timestamp the
    ingestion layer stores is already UTC, and silently re-interpreting one as
    Asia/Kolkata would shift the certified timestamp by 5.5 hours on an investigator's
    laptop while leaving it unchanged on a UTC server -- the same evidence would then
    hash differently on two machines.
    """
    if isinstance(value, datetime):
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return aware.isoformat().replace("+00:00", "Z")
    return value.isoformat()


def _json_default(value: Any) -> Any:
    """Coerce the non-JSON types that reach us from SQLAlchemy rows and web3 responses."""
    if isinstance(value, datetime | date):
        return _iso_utc(value)
    if isinstance(value, Decimal):
        # str(), not float(): float() would round large wei values and change the digest.
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes | bytearray):
        return "0x" + bytes(value).hex()
    if isinstance(value, set | frozenset):
        return sorted(str(item) for item in value)
    return str(value)


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Render `payload` in a canonical form suitable for hashing.

    Keys are sorted and separators are compact, so two dicts holding the same content in
    a different insertion order produce the same string -- and therefore the same
    SHA-256. Without this, merely re-reading a record through a different query (which
    may return its columns in another order) would look like tampering.
    """
    return json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of_record(record: EvidenceRecord) -> str:
    """SHA-256 digest of a single evidence record.

    The identity fields are hashed alongside the payload: hashing the payload alone
    would let an identical transaction body be re-labelled with another record_id or
    attributed to a different RPC source without the digest changing.
    """
    envelope = {
        "record_id": record.record_id,
        "record_type": record.record_type,
        "source": record.source,
        "payload": record.payload,
    }
    return _sha256_hex(canonical_json(envelope))


def merkle_root(hashes: Sequence[str]) -> str:
    """Compute the Merkle root over `hashes` (pairwise SHA-256, last node duplicated).

    An odd level duplicates its final node -- the convention Bitcoin uses -- so every
    level pairs cleanly. An empty record set yields sha256(b"").
    """
    if not hashes:
        return EMPTY_HASH

    level = list(hashes)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [_sha256_hex(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def build_hash_chain(hashes: Sequence[str]) -> tuple[str, ...]:
    """Build the running hash chain h_i = sha256(h_{i-1} || hash_i).

    The chain is what makes *position* tamper-evident: in a tree whose leaves repeat, the
    Merkle root alone need not change when two records are swapped, whereas every link
    from the affected position onwards changes here.
    """
    chain: list[str] = []
    previous = EMPTY_HASH
    for record_hash in hashes:
        previous = _sha256_hex(previous + record_hash)
        chain.append(previous)
    return tuple(chain)


def _default_system_metadata(generated_at: datetime) -> dict[str, Any]:
    """Environment facts the court needs in order to identify the producing system."""
    return {
        "software": "TRACE-X Blockchain Forensics Platform",
        "software_version": CERTIFICATE_FORMAT_VERSION,
        "certificate_format_version": CERTIFICATE_FORMAT_VERSION,
        "extraction_timestamp_utc": _iso_utc(generated_at),
        "host": platform.node(),
        "operating_system": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "hash_algorithm": "SHA-256",
        "byte_order": sys.byteorder,
    }


def _build_declaration(
    *,
    case_number: str,
    investigating_officer: str,
    record_count: int,
    merkle_root_hex: str,
    chain_tip: str,
    generated_at: datetime,
) -> str:
    """The formal statutory declaration, in the register a court expects."""
    extracted_at = _iso_utc(generated_at)
    return (
        f"I, {investigating_officer}, holding office in the Cyber Crime Investigation Division "
        "and being the person lawfully in charge of the operation of the TRACE-X Blockchain "
        f"Forensics Platform in respect of Case No. {case_number}, do hereby solemnly affirm "
        "and declare as follows:\n\n"
        f"1. That the electronic records annexed to this certificate, {record_count} in number "
        "and enumerated in Part A hereof, were produced by the said computer system during the "
        "period over which it was used regularly to store and process information for the "
        "purposes of the activities regularly carried on by this office.\n\n"
        "2. That the information contained in the said electronic records was derived from "
        "public distributed ledgers through the node and provider endpoints enumerated in "
        "Part C hereof, and was fed into the said computer system in the ordinary course of "
        "the said activities.\n\n"
        "3. That throughout the material part of the said period the computer was operating "
        "properly; and that where it was not operating properly for any part of that period, "
        "such fact did not affect the electronic records or the accuracy of their contents.\n\n"
        "4. That each electronic record has been reduced to a SHA-256 message digest, that the "
        f"said digests have been consolidated into the Merkle root {merkle_root_hex} and into "
        f"the hash chain terminating at {chain_tip}, and that any alteration, substitution, "
        "deletion or re-ordering of the said records after the time of extraction, being "
        f"{extracted_at}, would necessarily cause the said digests, root and chain to differ "
        "upon re-computation by any independent examiner.\n\n"
        "5. That this certificate is issued under Section 63 of the Bharatiya Sakshya "
        "Adhiniyam, 2023 (corresponding to Section 65B of the Indian Evidence Act, 1872), and "
        "the statements made herein are true to the best of my knowledge and belief."
    )


def build_certificate(
    records: Sequence[EvidenceRecord],
    *,
    case_number: str,
    investigating_officer: str,
    system_metadata: Mapping[str, Any] | None = None,
    certificate_id: str | None = None,
    generated_at: datetime | None = None,
) -> EvidenceCertificate:
    """Certify `records` under Section 63 BSA 2023 / Section 65B IEA 1872."""
    ts = generated_at or datetime.now(tz=UTC)

    record_hashes = tuple(sha256_of_record(record) for record in records)
    root = merkle_root(record_hashes)
    chain = build_hash_chain(record_hashes)
    tip = chain[-1] if chain else EMPTY_HASH

    # Derived from the evidence, never a uuid4: re-certifying the same records must yield
    # the same reference number, otherwise two printouts of one exhibit look to the court
    # like two different exhibits.
    ref_id = certificate_id or f"TRX-S63-{ts.strftime('%Y%m%d')}-{root[:10].upper()}"

    metadata = _default_system_metadata(ts)
    if system_metadata:
        metadata.update(dict(system_metadata))

    certificate = EvidenceCertificate(
        certificate_id=ref_id,
        generated_at=ts,
        case_number=case_number,
        investigating_officer=investigating_officer,
        record_count=len(records),
        record_hashes=record_hashes,
        merkle_root=root,
        hash_chain=chain,
        chain_tip=tip,
        system_metadata=metadata,
        declaration=_build_declaration(
            case_number=case_number,
            investigating_officer=investigating_officer,
            record_count=len(records),
            merkle_root_hex=root,
            chain_tip=tip,
            generated_at=ts,
        ),
    )

    logger.info(
        "evidence_certificate_built",
        certificate_id=ref_id,
        case_number=case_number,
        record_count=len(records),
        merkle_root=root,
    )
    return certificate


def verify_certificate(
    certificate: EvidenceCertificate,
    records: Sequence[EvidenceRecord],
) -> tuple[bool, list[str]]:
    """Re-compute every digest in `certificate` from `records`.

    Returns `(True, [])` when the evidence is untouched, otherwise `(False, reasons)`
    where each reason names precisely what diverged -- including the *index* of every
    record whose digest no longer matches. That index is the answer the Investigating
    Officer gives in cross-examination when asked which exhibit was altered.
    """
    problems: list[str] = []

    recomputed = [sha256_of_record(record) for record in records]

    if certificate.record_count != len(records):
        problems.append(
            f"record count mismatch: certificate declares {certificate.record_count} "
            f"record(s), {len(records)} record(s) supplied for verification"
        )

    for index in range(max(len(certificate.record_hashes), len(recomputed))):
        certified = (
            certificate.record_hashes[index] if index < len(certificate.record_hashes) else None
        )
        actual = recomputed[index] if index < len(recomputed) else None

        if certified is None:
            problems.append(
                f"record {index} (record_id={records[index].record_id!r}) is not covered by the "
                f"certificate: recomputed hash {actual}"
            )
        elif actual is None:
            problems.append(
                f"record {index} is missing from the evidence supplied: the certificate holds "
                f"hash {certified}"
            )
        elif certified != actual:
            problems.append(
                f"record {index} (record_id={records[index].record_id!r}) hash mismatch: "
                f"certificate holds {certified}, recomputed {actual}"
            )

    actual_root = merkle_root(recomputed)
    if actual_root != certificate.merkle_root:
        problems.append(
            f"merkle root mismatch: certificate holds {certificate.merkle_root}, "
            f"recomputed {actual_root}"
        )

    actual_chain = build_hash_chain(recomputed)
    if actual_chain != certificate.hash_chain:
        first_broken = next(
            (
                i
                for i in range(max(len(actual_chain), len(certificate.hash_chain)))
                if i >= len(actual_chain)
                or i >= len(certificate.hash_chain)
                or actual_chain[i] != certificate.hash_chain[i]
            ),
            0,
        )
        problems.append(
            f"hash chain diverges from record {first_broken} onwards: record {first_broken} or a "
            f"record preceding it was altered, removed or re-ordered after extraction"
        )

    actual_tip = actual_chain[-1] if actual_chain else EMPTY_HASH
    if actual_tip != certificate.chain_tip:
        problems.append(
            f"chain tip mismatch: certificate holds {certificate.chain_tip}, "
            f"recomputed {actual_tip}"
        )

    expected_declaration = _build_declaration(
        case_number=certificate.case_number,
        investigating_officer=certificate.investigating_officer,
        record_count=certificate.record_count,
        merkle_root_hex=certificate.merkle_root,
        chain_tip=certificate.chain_tip,
        generated_at=certificate.generated_at,
    )
    if certificate.declaration != expected_declaration:
        problems.append(
            "declaration text does not match the certified case number, officer, record count, "
            "merkle root and chain tip: the certificate document itself has been edited"
        )

    if problems:
        logger.warning(
            "evidence_certificate_verification_failed",
            certificate_id=certificate.certificate_id,
            case_number=certificate.case_number,
            problem_count=len(problems),
        )
        return False, problems

    return True, []


# Held apart from the f-string that renders the document: inside an f-string every CSS
# brace would have to be doubled, which makes the stylesheet unreadable and unmaintainable.
_CERTIFICATE_CSS = """
    @page {
        size: a4 portrait;
        margin: 18mm 16mm 18mm 16mm;
    }
    body {
        font-family: Helvetica, Arial, sans-serif;
        color: #111;
        font-size: 9.5pt;
        line-height: 1.4;
        margin: 0;
        padding: 0;
    }
    .header-table {
        width: 100%;
        border-bottom: 2px solid #1e293b;
        padding-bottom: 10px;
        margin-bottom: 16px;
    }
    .agency-title {
        font-size: 14pt;
        font-weight: bold;
        text-transform: uppercase;
        color: #0f172a;
        margin: 0;
    }
    .agency-sub {
        font-size: 8.5pt;
        color: #475569;
        margin-top: 2px;
    }
    .notice-badge {
        background-color: #0f766e;
        color: #ffffff;
        font-weight: bold;
        font-size: 8pt;
        padding: 4px 8px;
        border-radius: 4px;
        display: inline-block;
        text-align: right;
    }
    .order-title {
        text-align: center;
        font-size: 12pt;
        font-weight: bold;
        text-transform: uppercase;
        margin: 14px 0 14px 0;
        color: #134e4a;
        letter-spacing: 0.5px;
    }
    .info-box {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 8px 12px;
        border-radius: 4px;
        margin-bottom: 14px;
    }
    .field-label {
        font-weight: bold;
        color: #334155;
        width: 160px;
    }
    .section-heading {
        font-size: 10pt;
        font-weight: bold;
        color: #1e293b;
        border-bottom: 1px solid #cbd5e1;
        padding-bottom: 3px;
        margin-top: 14px;
        margin-bottom: 6px;
        text-transform: uppercase;
    }
    p {
        margin: 0 0 8px 0;
        text-align: justify;
    }
    .hash-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 8px;
        margin-bottom: 12px;
    }
    .hash-table th {
        background-color: #0f172a;
        color: #ffffff;
        font-size: 8pt;
        font-weight: bold;
        padding: 6px 4px;
        border: 1px solid #0f172a;
        text-align: left;
    }
    .hash-table td {
        font-size: 7.5pt;
        padding: 4px;
        border: 1px solid #ccc;
        vertical-align: top;
    }
    .mono {
        font-family: Courier, monospace;
        word-wrap: break-word;
    }
    .root-callout {
        background-color: #ecfdf5;
        border-left: 4px solid #0f766e;
        padding: 8px 10px;
        margin: 12px 0;
        font-size: 8.5pt;
        color: #064e3b;
    }
    .declaration {
        border: 1px solid #cbd5e1;
        background-color: #fffbeb;
        padding: 10px 12px;
        font-size: 9pt;
        white-space: pre-wrap;
        text-align: justify;
    }
    .signature-table {
        width: 100%;
        margin-top: 24px;
        page-break-inside: avoid;
    }
    .sig-line {
        border-top: 1px solid #334155;
        width: 240px;
        margin-top: 42px;
        padding-top: 4px;
        font-size: 8.5pt;
        color: #334155;
    }
    .stamp-box {
        border: 2px dashed #0f766e;
        color: #0f766e;
        padding: 8px;
        text-align: center;
        font-size: 8pt;
        font-weight: bold;
        width: 240px;
    }
"""


def generate_certificate_html(certificate: EvidenceCertificate) -> str:
    """Render the certificate as court-ready HTML."""
    date_str = certificate.generated_at.strftime("%B %d, %Y")
    time_str = _iso_utc(certificate.generated_at)

    hash_rows = []
    for index, record_hash in enumerate(certificate.record_hashes):
        chain_link = (
            certificate.hash_chain[index] if index < len(certificate.hash_chain) else EMPTY_HASH
        )
        hash_rows.append(
            f"""
        <tr>
            <td style="text-align: center;">{index}</td>
            <td class="mono">{_escape(record_hash)}</td>
            <td class="mono">{_escape(chain_link)}</td>
        </tr>
        """
        )

    hash_table_body = "".join(hash_rows) or (
        '<tr><td colspan="3" style="padding: 12px; text-align: center; color: #666;">'
        "No electronic records were tendered with this certificate.</td></tr>"
    )

    metadata_rows = "".join(
        f"""
        <tr>
            <td class="field-label">{_escape(key)}</td>
            <td class="mono">{_escape(value)}</td>
        </tr>
        """
        for key, value in sorted(certificate.system_metadata.items())
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>Certificate u/s 63 BSA 2023 - {_escape(certificate.case_number)}</title>
<style>
{_CERTIFICATE_CSS}
</style>
</head>
<body>

<table class="header-table">
    <tr>
        <td style="vertical-align: top;">
            <p class="agency-title">Cyber Crime Investigation Division</p>
            <p class="agency-sub">Financial Intelligence &amp; Digital Forensics Command |
                TRACE-X Intelligence Unit</p>
            <p class="agency-sub">Statutory Jurisdiction: Section 63, Bharatiya Sakshya
                Adhiniyam, 2023</p>
        </td>
        <td style="vertical-align: top; text-align: right;">
            <span class="notice-badge">ELECTRONIC EVIDENCE CERTIFICATE</span>
            <p style="font-size: 8pt; color: #64748b; margin-top: 6px;">
                Certificate No: <strong>{_escape(certificate.certificate_id)}</strong><br/>
                Date: {_escape(date_str)}<br/>
                Time: {_escape(time_str)}
            </p>
        </td>
    </tr>
</table>

<div class="order-title">
    CERTIFICATE UNDER SECTION 63 OF THE BHARATIYA SAKSHYA ADHINIYAM, 2023<br/>
    <span style="font-size: 9pt; font-weight: normal; color: #475569;">
        (CORRESPONDING TO SECTION 65B OF THE INDIAN EVIDENCE ACT, 1872)
    </span>
</div>

<div class="info-box">
    <table style="width: 100%; font-size: 9pt;">
        <tr>
            <td class="field-label">CASE NUMBER:</td>
            <td><strong>{_escape(certificate.case_number)}</strong></td>
        </tr>
        <tr>
            <td class="field-label">INVESTIGATING OFFICER:</td>
            <td><strong>{_escape(certificate.investigating_officer)}</strong></td>
        </tr>
        <tr>
            <td class="field-label">RECORDS CERTIFIED:</td>
            <td><strong>{certificate.record_count}</strong></td>
        </tr>
        <tr>
            <td class="field-label">EXTRACTED AT (UTC):</td>
            <td class="mono">{_escape(time_str)}</td>
        </tr>
    </table>
</div>

<div class="section-heading">Part A &mdash; SHA-256 Digest of Each Electronic Record</div>
<p style="font-size: 8.5pt; color: #475569;">
    Each record listed below was serialised in canonical form (UTF-8, keys lexically
    ordered, timestamps in ISO-8601 UTC) and reduced to a SHA-256 message digest at the
    moment of extraction. The cumulative column carries the running hash chain link
    computed over that digest and all digests preceding it.
</p>

<table class="hash-table">
    <thead>
        <tr>
            <th style="width: 6%; text-align: center;">#</th>
            <th style="width: 47%;">SHA-256 Digest of Record</th>
            <th style="width: 47%;">Cumulative Hash Chain Link</th>
        </tr>
    </thead>
    <tbody>
        {hash_table_body}
    </tbody>
</table>

<div class="section-heading">Part B &mdash; Merkle Root and Hash Chain of the Record Set</div>
<div class="root-callout">
    <strong>MERKLE ROOT (SHA-256):</strong>
    <span class="mono">{_escape(certificate.merkle_root)}</span><br/>
    <strong>HASH CHAIN TIP (SHA-256):</strong>
    <span class="mono">{_escape(certificate.chain_tip)}</span><br/>
    <strong>CHAIN LENGTH:</strong> {len(certificate.hash_chain)} link(s)
</div>
<p style="font-size: 8.5pt; color: #475569;">
    The Merkle root is computed by pairwise SHA-256 reduction of the record digests, the
    final node of an odd level being duplicated. The hash chain is computed as
    h(i) = SHA-256(h(i-1) || digest(i)). Any alteration, substitution, deletion or
    re-ordering of a certified record after extraction changes the root and breaks the
    chain from the affected position onwards, and is therefore detectable upon
    re-computation by an independent examiner.
</p>

<div class="section-heading">Part C &mdash; System Environment Metadata</div>
<table class="hash-table">
    <thead>
        <tr>
            <th style="width: 32%;">Parameter</th>
            <th style="width: 68%;">Recorded Value</th>
        </tr>
    </thead>
    <tbody>
        {metadata_rows}
    </tbody>
</table>

<div class="section-heading">Part D &mdash; Declaration of the Investigating Officer</div>
<div class="declaration">{_escape(certificate.declaration)}</div>

<table class="signature-table">
    <tr>
        <td style="vertical-align: top; width: 50%;">
            <div class="stamp-box">
                DIGITALLY CERTIFIED BY TRACE-X<br/>
                FORENSIC ENGINE VERIFICATION<br/>
                CERT: {_escape(certificate.certificate_id)}<br/>
                ROOT: {_escape(certificate.merkle_root[:32])}
            </div>
        </td>
        <td style="vertical-align: top; width: 50%; text-align: right;">
            <div class="sig-line" style="float: right; text-align: left;">
                <strong>Signature of the Investigating Officer</strong><br/>
                Name: {_escape(certificate.investigating_officer)}<br/>
                Designation: ____________________________<br/>
                Date: {_escape(date_str)}<br/>
                Place: ____________________________
            </div>
        </td>
    </tr>
</table>

</body>
</html>
"""


def generate_certificate_pdf(certificate: EvidenceCertificate) -> bytes:
    """Render the certificate HTML directly into valid PDF bytes."""
    html_str = generate_certificate_html(certificate)

    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        logger.error("xhtml2pdf_missing", detail=str(e))
        raise RuntimeError("xhtml2pdf is required for PDF generation") from e

    output = BytesIO()
    result = pisa.CreatePDF(src=html_str, dest=output, encoding="utf-8")

    if result.err:
        logger.error(
            "pdf_creation_error",
            err=result.err,
            certificate_id=certificate.certificate_id,
        )
        raise RuntimeError(f"xhtml2pdf encountered error: {result.err}")

    pdf_bytes = output.getvalue()
    if not pdf_bytes.startswith(b"%PDF-"):
        raise RuntimeError("PDF generation failed to produce valid PDF header")

    return pdf_bytes
