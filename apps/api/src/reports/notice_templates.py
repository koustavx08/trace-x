"""
Statutory Notice and Law Enforcement Request templates for TRACE-X.

Generates court-admissible legal orders directed at Virtual Asset Service Providers (VASPs)
such as Binance, Kraken, Coinbase, and OKX under Section 91 of the Code of Criminal
Procedure, 1973 (CrPC) / Section 94 of Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS).
"""

from __future__ import annotations

import html
from datetime import datetime
from io import BytesIO
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def _escape(val: Any) -> str:
    return html.escape(str(val or ""))


def generate_statutory_notice_html(
    wallet_address: str,
    entity_name: str = "Virtual Asset Service Provider (VASP)",
    case_number: str = "TRX-LE-2026",
    case_title: str = "Investigation into Illicit Crypto Asset Diversion",
    crime_type: str = "Financial Fraud / Cyber Extortion",
    transactions: list[dict[str, Any]] | None = None,
    notice_id: str | None = None,
    generated_at: datetime | None = None,
    total_value_usd: float | None = None,
) -> str:
    """Generate professional HTML for a Section 91 CrPC notice to an exchange."""
    ts = generated_at or datetime.utcnow()
    date_str = ts.strftime("%B %d, %Y")
    time_str = ts.strftime("%H:%M:%S UTC")
    ref_id = notice_id or f"TRX-SEC91-{ts.strftime('%Y%m%d')}-{wallet_address[-6:].upper()}"

    tx_list = transactions or []
    if total_value_usd is None:
        total_value_usd = sum(float(t.get("value_usd") or 0.0) for t in tx_list)

    # Render table rows
    tx_rows = []
    for tx in tx_list[:15]:
        tx_hash = str(tx.get("tx_hash") or "")
        short_hash = f"{tx_hash[:10]}...{tx_hash[-8:]}" if len(tx_hash) > 18 else tx_hash
        from_addr = str(tx.get("from_address") or "")
        short_from = f"{from_addr[:8]}...{from_addr[-6:]}" if len(from_addr) > 14 else from_addr
        to_addr = str(tx.get("to_address") or "")
        short_to = f"{to_addr[:8]}...{to_addr[-6:]}" if len(to_addr) > 14 else to_addr
        val_usd = float(tx.get("value_usd") or 0.0)
        token = str(tx.get("token_symbol") or "ETH")
        block = str(tx.get("block_number") or "-")
        tx_time = str(tx.get("timestamp") or "")[:19].replace("T", " ")

        tx_rows.append(f"""
        <tr>
            <td style="font-family: monospace; font-size: 8pt; padding: 4px; border: 1px solid #ccc;">{short_hash}</td>
            <td style="font-size: 8pt; padding: 4px; border: 1px solid #ccc; text-align: center;">{block}</td>
            <td style="font-size: 8pt; padding: 4px; border: 1px solid #ccc;">{tx_time}</td>
            <td style="font-family: monospace; font-size: 8pt; padding: 4px; border: 1px solid #ccc;">{short_from}</td>
            <td style="font-family: monospace; font-size: 8pt; padding: 4px; border: 1px solid #ccc;">{short_to}</td>
            <td style="font-size: 8pt; padding: 4px; border: 1px solid #ccc; text-align: right; font-weight: bold;">${val_usd:,.2f}</td>
            <td style="font-size: 8pt; padding: 4px; border: 1px solid #ccc; text-align: center;">{token}</td>
        </tr>
        """)

    tx_table_body = (
        "".join(tx_rows)
        if tx_rows
        else """
    <tr><td colspan="7" style="padding: 12px; text-align: center; color: #666; border: 1px solid #ccc;">No direct transaction entries recorded.</td></tr>
    """
    )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>Statutory Notice u/s 91 CrPC - {entity_name}</title>
<style>
    @page {{
        size: a4 portrait;
        margin: 18mm 16mm 18mm 16mm;
    }}
    body {{
        font-family: Helvetica, Arial, sans-serif;
        color: #111;
        font-size: 9.5pt;
        line-height: 1.4;
        margin: 0;
        padding: 0;
    }}
    .header-table {{
        width: 100%;
        border-bottom: 2px solid #1e293b;
        padding-bottom: 10px;
        margin-bottom: 16px;
    }}
    .agency-title {{
        font-size: 14pt;
        font-weight: bold;
        text-transform: uppercase;
        color: #0f172a;
        margin: 0;
    }}
    .agency-sub {{
        font-size: 8.5pt;
        color: #475569;
        margin-top: 2px;
    }}
    .notice-badge {{
        background-color: #7c3aed;
        color: #ffffff;
        font-weight: bold;
        font-size: 8pt;
        padding: 4px 8px;
        border-radius: 4px;
        display: inline-block;
        text-align: right;
    }}
    .order-title {{
        text-align: center;
        font-size: 12pt;
        font-weight: bold;
        text-transform: uppercase;
        margin: 14px 0 14px 0;
        color: #1e1b4b;
        letter-spacing: 0.5px;
    }}
    .info-box {{
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 8px 12px;
        border-radius: 4px;
        margin-bottom: 14px;
    }}
    .field-label {{
        font-weight: bold;
        color: #334155;
        width: 120px;
    }}
    .section-heading {{
        font-size: 10pt;
        font-weight: bold;
        color: #1e293b;
        border-bottom: 1px solid #cbd5e1;
        padding-bottom: 3px;
        margin-top: 14px;
        margin-bottom: 6px;
        text-transform: uppercase;
    }}
    p {{
        margin: 0 0 8px 0;
        text-align: justify;
    }}
    ol, ul {{
        margin: 0 0 10px 18px;
        padding: 0;
    }}
    li {{
        margin-bottom: 4px;
    }}
    .tx-table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 8px;
        margin-bottom: 12px;
    }}
    .tx-table th {{
        background-color: #0f172a;
        color: #ffffff;
        font-size: 8pt;
        font-weight: bold;
        padding: 6px 4px;
        border: 1px solid #0f172a;
        text-align: left;
    }}
    .warning-callout {{
        background-color: #fef2f2;
        border-left: 4px solid #ef4444;
        padding: 8px 10px;
        margin: 12px 0;
        font-size: 8.5pt;
        color: #991b1b;
    }}
    .signature-table {{
        width: 100%;
        margin-top: 24px;
        page-break-inside: avoid;
    }}
    .stamp-box {{
        border: 2px dashed #7c3aed;
        color: #7c3aed;
        padding: 8px;
        text-align: center;
        font-size: 8pt;
        font-weight: bold;
        width: 220px;
    }}
</style>
</head>
<body>

<table class="header-table">
    <tr>
        <td style="vertical-align: top;">
            <p class="agency-title">Cyber Crime Investigation Division</p>
            <p class="agency-sub">Financial Intelligence & Digital Forensics Command | TRACE-X Intelligence Unit</p>
            <p class="agency-sub">Statutory Jurisdiction: Section 91 Cr.P.C. / Section 94 BNSS, 2023</p>
        </td>
        <td style="vertical-align: top; text-align: right;">
            <span class="notice-badge">STATUTORY LEGAL ORDER</span>
            <p style="font-size: 8pt; color: #64748b; margin-top: 6px;">Ref No: <strong>{_escape(ref_id)}</strong><br/>Date: {_escape(date_str)}<br/>Time: {_escape(time_str)}</p>
        </td>
    </tr>
</table>

<div class="order-title">
    NOTICE UNDER SECTION 91 OF THE CODE OF CRIMINAL PROCEDURE, 1973<br/>
    <span style="font-size: 9pt; font-weight: normal; color: #475569;">
        (READ WITH SECTION 94 OF BHARATIYA NAGARIK SURAKSHA SANHITA, 2023)
    </span>
</div>

<div class="info-box">
    <table style="width: 100%; font-size: 9pt;">
        <tr>
            <td class="field-label" style="vertical-align: top;">TO:</td>
            <td>
                <strong>The Nodal Officer / Law Enforcement Response Team</strong><br/>
                <strong>{_escape(entity_name)}</strong><br/>
                Compliance, Investigations &amp; Global Asset Preservation Department
            </td>
        </tr>
        <tr>
            <td class="field-label" style="padding-top: 6px;">CASE REF:</td>
            <td style="padding-top: 6px;"><strong>{_escape(case_number)}</strong> ({_escape(case_title)})</td>
        </tr>
        <tr>
            <td class="field-label">OFFENSE TYPE:</td>
            <td>{_escape(crime_type)} (IPC Sec 419/420, IT Act Sec 66C/66D)</td>
        </tr>
        <tr>
            <td class="field-label">TARGET WALLET:</td>
            <td><code style="font-family: monospace; font-weight: bold; color: #7c3aed; font-size: 9.5pt;">{_escape(wallet_address)}</code></td>
        </tr>
    </table>
</div>

<p>
    <strong>SUBJECT: MANDATORY PRODUCTION OF DOCUMENTS, COMPLETE KYC RECORDS, ACCESS LOGS, AND IMMEDIATE FREEZING OF VIRTUAL ASSETS ASSOCIATED WITH BENEFICIARY ACCOUNT.</strong>
</p>

<p>
    WHEREAS, an official investigation is being conducted into the unauthorized laundering, diversion, and off-ramping of stolen digital assets under Case Reference <strong>{_escape(case_number)}</strong>.
</p>

<p>
    WHEREAS, advanced blockchain forensic tracing executed by the TRACE-X Engine has established that illicit proceeds totaling approximately <strong>${total_value_usd:,.2f} USD</strong> were channeled across on-chain intermediary hops directly into the custodial deposit architecture of <strong>{_escape(entity_name)}</strong> via deposit address <strong>{_escape(wallet_address)}</strong>.
</p>

<div class="section-heading">1. Cryptographic Evidence of Inflow</div>
<p style="font-size: 8.5pt; color: #475569;">
    The table below summarizes the on-chain transactions transferring tainted funds into your exchange's custody:
</p>

<table class="tx-table">
    <thead>
        <tr>
            <th>Tx Hash</th>
            <th>Block</th>
            <th>Timestamp (UTC)</th>
            <th>From Address</th>
            <th>To (Deposit Address)</th>
            <th style="text-align: right;">Value (USD)</th>
            <th style="text-align: center;">Token</th>
        </tr>
    </thead>
    <tbody>
        {tx_table_body}
    </tbody>
</table>

<div class="section-heading">2. Statutory Directives &amp; Requirements</div>
<p>
    In exercise of statutory powers under Section 91 of the Code of Criminal Procedure, 1973 (Cr.P.C.), you are hereby summoned and strictly directed to furnish and execute the following <strong>within twenty-four (24) hours</strong> of receipt of this notice:
</p>

<ol>
    <li>
        <strong>Immediate Administrative Asset Freeze:</strong> Immediately restrict, freeze, and suspend all outbound withdrawals, internal transfers, P2P trades, and fiat conversions for the internal User ID (UID) / customer account mapped to deposit address <code style="font-family: monospace;">{_escape(wallet_address)}</code>.
    </li>
    <li>
        <strong>Production of Complete KYC Dossier:</strong> Furnish certified copies of:
        <ul>
            <li>Full legal name, date of birth, nationality, and verified primary residential address.</li>
            <li>Government-issued identity documents (Passport, National ID, Aadhaar, Driving License) submitted during onboarding.</li>
            <li>Registered email address, contact telephone number, and multi-factor authentication details.</li>
        </ul>
    </li>
    <li>
        <strong>Financial &amp; Banking Linkage:</strong> Provide details of all linked bank accounts, credit/debit cards, payment gateways, and secondary withdrawal crypto addresses associated with this user.
    </li>
    <li>
        <strong>Access &amp; Device Footprint:</strong> Provide complete IP connection logs (IPv4/IPv6), port numbers, timestamps, and browser/device fingerprints for all logins to this account over the preceding 90 days.
    </li>
    <li>
        <strong>Preservation Order:</strong> Maintain all transaction logs, chat histories, and support tickets under strict legal preservation until further direction from this office or a competent court of law.
    </li>
</ol>

<div class="warning-callout">
    <strong>STATUTORY WARNING:</strong> Non-compliance or failure to furnish the required particulars within the stipulated time frame constitutes a punishable offense under Section 175 and Section 176 of the Indian Penal Code (IPC) / Sections 210 and 211 of Bharatiya Nyaya Sanhita (BNS), 2023, attracting penal action and administrative sanctions.
</div>

<table class="signature-table">
    <tr>
        <td style="vertical-align: top; width: 55%;">
            <div class="stamp-box">
                DIGITALLY CERTIFIED BY TRACE-X<br/>
                FORENSIC ENGINE VERIFICATION<br/>
                HASH: {_escape(ref_id)}<br/>
                TIMESTAMP: {_escape(time_str)}
            </div>
        </td>
        <td style="vertical-align: top; text-align: right; width: 45%;">
            <p style="margin: 0; font-size: 9pt;">
                <strong>Investigating Officer (Cyber Forensics)</strong><br/>
                Cyber Crime &amp; Economic Offenses Unit<br/>
                Financial Intelligence Command<br/>
                TRACE-X Law Enforcement System
            </p>
        </td>
    </tr>
</table>

</body>
</html>
"""
    return html_content


def generate_statutory_notice_pdf(
    wallet_address: str,
    entity_name: str = "Virtual Asset Service Provider (VASP)",
    case_number: str = "TRX-LE-2026",
    case_title: str = "Investigation into Illicit Crypto Asset Diversion",
    crime_type: str = "Financial Fraud / Cyber Extortion",
    transactions: list[dict[str, Any]] | None = None,
    notice_id: str | None = None,
    generated_at: datetime | None = None,
    total_value_usd: float | None = None,
) -> bytes:
    """Render statutory notice HTML directly into valid PDF bytes."""
    html_str = generate_statutory_notice_html(
        wallet_address=wallet_address,
        entity_name=entity_name,
        case_number=case_number,
        case_title=case_title,
        crime_type=crime_type,
        transactions=transactions,
        notice_id=notice_id,
        generated_at=generated_at,
        total_value_usd=total_value_usd,
    )

    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        logger.error("xhtml2pdf_missing", detail=str(e))
        raise RuntimeError("xhtml2pdf is required for PDF generation") from e

    output = BytesIO()
    result = pisa.CreatePDF(src=html_str, dest=output, encoding="utf-8")

    if result.err:
        logger.error("pdf_creation_error", err=result.err)
        raise RuntimeError(f"xhtml2pdf encountered error: {result.err}")

    pdf_bytes = output.getvalue()
    if not pdf_bytes.startswith(b"%PDF-"):
        raise RuntimeError("PDF generation failed to produce valid PDF header")

    return pdf_bytes
