"""
Statutory Notice and Law Enforcement Request templates for TRACE-X.

Generates court-admissible legal orders directed at Virtual Asset Service Providers (VASPs)
such as Binance, Kraken, Coinbase, and OKX under:
- Section 106 of Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS) / Section 102 Cr.P.C. (Asset Seizure)
- Section 106(3) & Section 94 of BNSS, 2023 / Section 102(3) & 91 Cr.P.C. (Total Account Debit Lien)
- Section 94 & Section 106(3) of BNSS, 2023 (Targeted Debit Lien & Bonafide P2P Merchant Requisition)
- Section 91 of Code of Criminal Procedure, 1973 (Cr.P.C.) (Legacy Fallback)
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
    notice_type: str = "section_106_bnss_seizure",
) -> str:
    """Generate professional court-admissible HTML for statutory notices to an exchange."""
    ts = generated_at or datetime.utcnow()
    date_str = ts.strftime("%B %d, %Y")
    time_str = ts.strftime("%H:%M:%S UTC")

    # Prefix ref_id by notice type
    type_code = "SEC106-SZ"
    if "debit_lien" in notice_type or "106_3" in notice_type:
        type_code = "SEC106-DL"
    elif "targeted_lien" in notice_type or "94" in notice_type:
        type_code = "SEC94-TL"
    elif "91" in notice_type:
        type_code = "SEC91"

    ref_id = notice_id or f"TRX-{type_code}-{ts.strftime('%Y%m%d')}-{wallet_address[-6:].upper()}"

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

    # Differentiate Content based on Notice Type
    if notice_type in ("section_106_bnss_seizure", "section_106_bnss_freeze"):
        # HIGH-RISK 1: ASSET SEIZURE ORDER
        badge_text = "EMERGENCY ASSET SEIZURE ORDER (100% CRYPTO SEIZURE)"
        badge_bg = "#dc2626"
        agency_sub_law = "Statutory Jurisdiction: Section 106 BNSS, 2023 / Section 102 Cr.P.C. (Seizure of Property)"
        order_title = """
        ORDER OF SEIZURE OF VIRTUAL ASSETS UNDER SECTION 106 OF BHARATIYA NAGARIK SURAKSHA SANHITA, 2023 (BNSS)<br/>
        <span style="font-size: 8.5pt; font-weight: normal; color: #475569;">
            (CORRESPONDING TO SECTION 102 OF THE CODE OF CRIMINAL PROCEDURE, 1973 - Cr.P.C.)
        </span><br/>
        <span style="font-size: 8pt; font-weight: bold; color: #b91c1c;">
            READ WITH SECTION 79(3)(b) &amp; SECTION 69B OF THE INFORMATION TECHNOLOGY ACT, 2000
        </span>
        """
        subject_text = (
            "MANDATORY CONFISCATION, TOTAL ASSET SEIZURE, AND IMMEDIATE CUSTODIAL TRANSFER OF ALL "
            "CRYPTOCURRENCY HOLDINGS ASSOCIATED WITH SUSPECT MULE ACCOUNT."
        )
        directives_html = f"""
        <ol>
            <li>
                <strong>Immediate Total Asset Seizure:</strong> In exercise of powers conferred under Section 106 of the Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS), you are strictly directed to immediately freeze, seize, and attach 100% of all cryptocurrency tokens, virtual assets, staking contracts, and derivative positions credited to or held by the internal User ID (UID) mapped to deposit address <code style="font-family: monospace;">{_escape(wallet_address)}</code>.
            </li>
            <li>
                <strong>Custodial Escrow Segregation:</strong> Sequester and transfer all seized virtual assets into an isolated cold-storage custodial escrow wallet maintained under police seal, pending judicial forfeiture proceedings under Section 107 BNSS.
            </li>
            <li>
                <strong>Urgent KYC Dossier Production (6-Hour Turnaround):</strong> Furnish certified true copies of:
                <ul>
                    <li>Primary onboarding identity documents (Passport, National ID, Aadhaar, Driving License, Pan Card).</li>
                    <li>Biometric/facial liveness verification files and onboarding video-KYC recordings.</li>
                    <li>Registered phone number, alternate phone numbers, email addresses, and 2FA authentication logs.</li>
                </ul>
            </li>
            <li>
                <strong>Telemetry &amp; Device Forensics:</strong> Furnish complete IP connection logs (IPv4/IPv6, VPN/Tor exit node flags), port numbers, timestamps, IMEI/MAC addresses, and browser device fingerprints for all logins over the preceding 90 days.
            </li>
            <li>
                <strong>Immediate Prohibition of Counter-Actions:</strong> No asset release, liquidation, or internal transfers shall be permitted without prior written authorization from this office or the jurisdictional Magistrate.
            </li>
        </ol>
        """
        warning_html = """
        <strong>STATUTORY WARNING:</strong> Non-compliance or failure to execute this seizure order within six (6) hours of receipt constitutes willful obstruction of police investigation and is punishable under Section 210, Section 211, and Section 223 of Bharatiya Nyaya Sanhita, 2023 (BNS) (formerly Sections 175, 176, and 188 IPC), along with regulatory sanctions under Section 79(3)(b) of the Information Technology Act, 2000.
        """

    elif notice_type == "section_106_bnss_debit_lien":
        # HIGH-RISK 2: TOTAL ACCOUNT DEBIT LIEN ORDER
        badge_text = "TOTAL ACCOUNT DEBIT LIEN ORDER (FIAT & OUTFLOW FREEZE)"
        badge_bg = "#b91c1c"
        agency_sub_law = "Statutory Jurisdiction: Section 106(3) & Section 94 BNSS, 2023 / Section 102(3) & 91 Cr.P.C."
        order_title = """
        TOTAL DEBIT LIEN & FINANCIAL REQUISITION ORDER UNDER SECTION 106(3) &amp; SECTION 94 BNSS, 2023<br/>
        <span style="font-size: 8.5pt; font-weight: normal; color: #475569;">
            (CORRESPONDING TO SECTION 102(3) &amp; SECTION 91 OF CODE OF CRIMINAL PROCEDURE, 1973 - Cr.P.C.)
        </span><br/>
        <span style="font-size: 8pt; font-weight: bold; color: #991b1b;">
            READ WITH SECTION 68E/68F NDPS ACT &amp; FIU-IND COMPLIANCE DIRECTIVES ON INTERMEDIARIES
        </span>
        """
        subject_text = (
            "IMMEDIATE ATTACHMENT AND TOTAL DEBIT LIEN ACROSS ALL FIAT BALANCES, LINKED BANK ACCOUNTS, "
            "PAYMENT RAILS, AND OUTBOUND CHANNELS OF BENEFICIARY ACCOUNT."
        )
        directives_html = f"""
        <ol>
            <li>
                <strong>Total Account Debit Lien:</strong> Immediately place an absolute, comprehensive debit lien across the entire User ID (UID) mapped to deposit address <code style="font-family: monospace;">{_escape(wallet_address)}</code>. You are strictly prohibited from releasing, transferring, or remitting any funds or fiat balances (INR, USD, EUR, etc.) credited to this account.
            </li>
            <li>
                <strong>Suspension of Fiat &amp; P2P Off-Ramping:</strong> Immediately suspend all linked bank withdrawal requests, IMPS/NEFT/RTGS rails, UPI handles, debit/credit cards, and active P2P merchant order advertisements associated with this UID.
            </li>
            <li>
                <strong>Production of Banking &amp; Remittance Trail (24 Hours):</strong> Furnish full banking details of all fiat inflows/outflows for this user:
                <ul>
                    <li>Verified bank name, account number, IFSC/SWIFT code, and account holder legal name.</li>
                    <li>Registered UPI VPA IDs and third-party payment gateway transaction references.</li>
                    <li>Complete historical list of all external blockchain withdrawal addresses ever utilized by this account.</li>
                </ul>
            </li>
            <li>
                <strong>Preservation of Account Ledger:</strong> Lock and preserve all internal ledger logs, order book interactions, trade fills, and audit trails under strict legal preservation.
            </li>
        </ol>
        """
        warning_html = """
        <strong>STATUTORY WARNING:</strong> Permitting outbound debits, dissipation of funds, or failing to enforce this lien constitutes a cognizable offense under Sections 210 and 211 of Bharatiya Nyaya Sanhita, 2023 (BNS), and exposes the reporting entity to accessory liability and regulatory referral to the Financial Intelligence Unit (FIU-IND).
        """

    elif notice_type == "section_94_bnss_targeted_lien":
        # LOW-RISK: TARGETED DEBIT LIEN & BONAFIDE MERCHANT REQUISITION
        badge_text = "TARGETED DEBIT LIEN & REQUISITION (INFLOW ONLY)"
        badge_bg = "#059669"
        agency_sub_law = (
            "Statutory Jurisdiction: Section 94 & Section 106(3) BNSS, 2023 / Section 91 Cr.P.C."
        )
        order_title = """
        TARGETED DEBIT LIEN &amp; EVIDENTIARY REQUISITION UNDER SECTION 94 &amp; SECTION 106(3) BNSS, 2023<br/>
        <span style="font-size: 8.5pt; font-weight: normal; color: #475569;">
            (CORRESPONDING TO SECTION 91 &amp; SECTION 102(3) OF CODE OF CRIMINAL PROCEDURE, 1973 - Cr.P.C.)
        </span><br/>
        <span style="font-size: 8pt; font-weight: bold; color: #047857;">
            READ WITH SECTION 317(1) BNS SAFE HARBOR FOR BONA FIDE COMMERCIAL TRANSFEREES
        </span>
        """
        subject_text = (
            f"TARGETED DEBIT LIEN RESTRICTED STRICTLY TO DISPUTED INFLOW SUM (${total_value_usd:,.2f}) "
            "AND REQUISITION OF P2P TRADE SLIPS &amp; COUNTERPARTY CHAT LOGS."
        )
        directives_html = f"""
        <ol>
            <li>
                <strong>Targeted Debit Lien (Inflow Sum Only):</strong> Place a targeted debit lien/hold strictly on the sum of <strong>${total_value_usd:,.2f} USD</strong> (or equivalent in USDT/fiat) received in connection with deposit address <code style="font-family: monospace;">{_escape(wallet_address)}</code>.
            </li>
            <li>
                <strong>Express Protection of Legitimate Trading &amp; Balances:</strong> <strong>DO NOT freeze the user's entire account</strong>, and DO NOT interrupt unrelated spot/derivative trading or withhold surplus legitimate balances exceeding the liened amount. This order is designed to preserve legitimate commercial operations while isolating disputed funds.
            </li>
            <li>
                <strong>Requisition of P2P Trade Dossier (72-Hour Response Window):</strong> Summons the user (via exchange compliance) to furnish verified documentation:
                <ul>
                    <li>P2P order matching slip, advertisement ID, order creation timestamp, and completion receipt.</li>
                    <li>Counterparty buyer/seller KYC identifiers, user handles, and communication/chat transcripts on the exchange's messaging platform.</li>
                    <li>Proof of payment verification (bank UTR reference number, payment screenshot, or fiat remittance gateway receipt).</li>
                </ul>
            </li>
            <li>
                <strong>Merchant Assessment &amp; Historical Standing:</strong> Provide user's 6-month trade volume, completion rate, account tenure, and merchant tier to determine eligibility under bona fide transferee protection rules.
            </li>
        </ol>
        <div style="background-color: #ecfdf5; border-left: 4px solid #10b981; padding: 8px 10px; margin: 10px 0; font-size: 8.5pt; color: #065f46;">
            <strong>BONA FIDE MERCHANT SAFE HARBOR (SEC 317(1) BNS):</strong> If compliance records substantiate that the account holder acted as a bona fide commercial counterparty without knowledge or constructive notice of stolen origin, the statutory lien may be resolved through civil interpleader or judicial release without criminal charges against the merchant.
        </div>
        """
        warning_html = """
        <strong>COMPLIANCE NOTICE:</strong> Please furnish the requisitioned P2P documentation within seventy-two (72) hours. Failure to respond or withholding records without cause may result in escalation to Section 106 BNSS full account seizure under Sections 210 and 211 of Bharatiya Nyaya Sanhita, 2023.
        """

    else:
        # LEGACY FALLBACK: SECTION 91 CrPC
        badge_text = "STATUTORY LEGAL ORDER"
        badge_bg = "#7c3aed"
        agency_sub_law = "Statutory Jurisdiction: Section 91 Cr.P.C. / Section 94 BNSS, 2023"
        order_title = """
        NOTICE UNDER SECTION 91 OF THE CODE OF CRIMINAL PROCEDURE, 1973<br/>
        <span style="font-size: 9pt; font-weight: normal; color: #475569;">
            (READ WITH SECTION 94 OF BHARATIYA NAGARIK SURAKSHA SANHITA, 2023)
        </span>
        """
        subject_text = (
            "MANDATORY PRODUCTION OF DOCUMENTS, COMPLETE KYC RECORDS, ACCESS LOGS, AND "
            "IMMEDIATE FREEZING OF VIRTUAL ASSETS ASSOCIATED WITH BENEFICIARY ACCOUNT."
        )
        directives_html = f"""
        <ol>
            <li>
                <strong>Immediate Administrative Asset Freeze:</strong> Immediately restrict, freeze, and suspend all outbound withdrawals, internal transfers, P2P trades, and fiat conversions for the internal User ID (UID) / customer account mapped to deposit address <code style="font-family: monospace;">{_escape(wallet_address)}</code>.
            </li>
            <li>
                <strong>Production of Complete KYC Dossier:</strong> Furnish certified copies of government identity documents, residential address, email, and mobile telephone numbers.
            </li>
            <li>
                <strong>Financial &amp; Banking Linkage:</strong> Provide details of all linked bank accounts, payment methods, and secondary withdrawal crypto addresses.
            </li>
            <li>
                <strong>Access &amp; Device Footprint:</strong> Provide complete IP connection logs (IPv4/IPv6), port numbers, timestamps, and browser/device fingerprints for all logins over the preceding 90 days.
            </li>
        </ol>
        """
        warning_html = """
        <strong>STATUTORY WARNING:</strong> Non-compliance or failure to furnish the required particulars within the stipulated time frame constitutes a punishable offense under Section 175 and Section 176 IPC / Sections 210 and 211 BNS, 2023.
        """

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>Statutory Legal Order - {_escape(entity_name)}</title>
<style>
    @page {{
        size: a4 portrait;
        margin: 16mm 14mm 16mm 14mm;
    }}
    body {{
        font-family: Helvetica, Arial, sans-serif;
        color: #111;
        font-size: 9pt;
        line-height: 1.35;
        margin: 0;
        padding: 0;
    }}
    .header-table {{
        width: 100%;
        border-bottom: 2px solid #1e293b;
        padding-bottom: 8px;
        margin-bottom: 12px;
    }}
    .agency-title {{
        font-size: 13pt;
        font-weight: bold;
        text-transform: uppercase;
        color: #0f172a;
        margin: 0;
    }}
    .agency-sub {{
        font-size: 8pt;
        color: #475569;
        margin-top: 2px;
    }}
    .notice-badge {{
        background-color: {badge_bg};
        color: #ffffff;
        font-weight: bold;
        font-size: 7.5pt;
        padding: 4px 8px;
        border-radius: 4px;
        display: inline-block;
        text-align: right;
    }}
    .order-title {{
        text-align: center;
        font-size: 11pt;
        font-weight: bold;
        text-transform: uppercase;
        margin: 10px 0 10px 0;
        color: #1e1b4b;
        letter-spacing: 0.3px;
        line-height: 1.3;
    }}
    .info-box {{
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 6px 10px;
        border-radius: 4px;
        margin-bottom: 10px;
    }}
    .field-label {{
        font-weight: bold;
        color: #334155;
        width: 120px;
    }}
    .section-heading {{
        font-size: 9.5pt;
        font-weight: bold;
        color: #1e293b;
        border-bottom: 1px solid #cbd5e1;
        padding-bottom: 2px;
        margin-top: 10px;
        margin-bottom: 5px;
        text-transform: uppercase;
    }}
    p {{
        margin: 0 0 6px 0;
        text-align: justify;
    }}
    ol, ul {{
        margin: 0 0 8px 16px;
        padding: 0;
    }}
    li {{
        margin-bottom: 3px;
    }}
    .tx-table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 6px;
        margin-bottom: 8px;
    }}
    .tx-table th {{
        background-color: #0f172a;
        color: #ffffff;
        font-size: 7.5pt;
        font-weight: bold;
        padding: 5px 4px;
        border: 1px solid #0f172a;
        text-align: left;
    }}
    .warning-callout {{
        background-color: #fef2f2;
        border-left: 4px solid #ef4444;
        padding: 6px 10px;
        margin: 10px 0;
        font-size: 8pt;
        color: #991b1b;
    }}
    .signature-table {{
        width: 100%;
        margin-top: 16px;
        page-break-inside: avoid;
    }}
    .stamp-box {{
        border: 2px dashed {badge_bg};
        color: {badge_bg};
        padding: 6px;
        text-align: center;
        font-size: 7.5pt;
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
            <p class="agency-sub">Financial Intelligence &amp; Digital Forensics Command | TRACE-X Intelligence Unit</p>
            <p class="agency-sub">{agency_sub_law}</p>
        </td>
        <td style="vertical-align: top; text-align: right;">
            <span class="notice-badge">{badge_text}</span>
            <p style="font-size: 7.5pt; color: #64748b; margin-top: 4px;">Ref No: <strong>{_escape(ref_id)}</strong><br/>Date: {_escape(date_str)}<br/>Time: {_escape(time_str)}</p>
        </td>
    </tr>
</table>

<div class="order-title">
    {order_title}
</div>

<div class="info-box">
    <table style="width: 100%; font-size: 8.5pt;">
        <tr>
            <td class="field-label" style="vertical-align: top;">TO:</td>
            <td>
                <strong>The Nodal Officer / Law Enforcement Response Team</strong><br/>
                <strong>{_escape(entity_name)}</strong><br/>
                Compliance, Investigations &amp; Global Asset Preservation Department
            </td>
        </tr>
        <tr>
            <td class="field-label" style="padding-top: 4px;">CASE REF:</td>
            <td style="padding-top: 4px;"><strong>{_escape(case_number)}</strong> ({_escape(case_title)})</td>
        </tr>
        <tr>
            <td class="field-label">OFFENSE TYPE:</td>
            <td>{_escape(crime_type)} (BNS Sec 318(4)/317/61(2), IT Act Sec 66C/66D)</td>
        </tr>
        <tr>
            <td class="field-label">TARGET WALLET:</td>
            <td><code style="font-family: monospace; font-weight: bold; color: {badge_bg}; font-size: 9pt;">{_escape(wallet_address)}</code></td>
        </tr>
    </table>
</div>

<p>
    <strong>SUBJECT: {subject_text}</strong>
</p>

<p>
    WHEREAS, an official investigation is being conducted into the unauthorized diversion, money laundering, and off-ramping of stolen digital assets under Case Reference <strong>{_escape(case_number)}</strong>.
</p>

<p>
    WHEREAS, advanced blockchain forensic tracing executed by the TRACE-X Forensics Engine has established that illicit proceeds totaling approximately <strong>${total_value_usd:,.2f} USD</strong> were channeled across on-chain intermediary hops directly into the custodial deposit architecture of <strong>{_escape(entity_name)}</strong> via deposit address <strong>{_escape(wallet_address)}</strong>.
</p>

<div class="section-heading">1. Cryptographic Evidence of Inflow</div>
<p style="font-size: 8pt; color: #475569;">
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
{directives_html}

<div class="warning-callout">
    {warning_html}
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
            <p style="margin: 0; font-size: 8.5pt;">
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
    notice_type: str = "section_106_bnss_seizure",
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
        notice_type=notice_type,
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
