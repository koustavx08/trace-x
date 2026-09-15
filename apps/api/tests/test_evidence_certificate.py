"""Tests for the Section 63 BSA 2023 / Section 65B IEA electronic-evidence certificate.

These exercise the hashing, the tamper detection and the rendered document. They touch
neither the database nor the network, so they run anywhere the package imports.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from src.reports.evidence_certificate import (
    EMPTY_HASH,
    EvidenceRecord,
    build_certificate,
    build_hash_chain,
    canonical_json,
    generate_certificate_html,
    generate_certificate_pdf,
    merkle_root,
    sha256_of_record,
    verify_certificate,
)

FIXED_TIME = datetime(2026, 3, 14, 9, 30, 0, tzinfo=UTC)
CASE_NUMBER = "TRX-LE-2026-0042"
OFFICER = "Inspector A. Sharma"


def _record(index: int, **overrides: Any) -> EvidenceRecord:
    fields: dict[str, Any] = {
        "record_id": f"tx-{index}",
        "record_type": "transaction",
        "payload": {
            "tx_hash": f"0x{index:064x}",
            "from_address": "0xabc0000000000000000000000000000000000001",
            "to_address": "0xdef0000000000000000000000000000000000002",
            "value_usd": 1250.5 * index,
            "block_number": 19_000_000 + index,
            "timestamp": datetime(2026, 3, 1, 12, 0, index, tzinfo=UTC),
        },
        "source": "https://eth-mainnet.g.alchemy.com/v2 (block 19000000)",
    }
    fields.update(overrides)
    return EvidenceRecord(**fields)


def _records(count: int) -> list[EvidenceRecord]:
    return [_record(i) for i in range(1, count + 1)]


def _certificate(records: list[EvidenceRecord]):
    return build_certificate(
        records,
        case_number=CASE_NUMBER,
        investigating_officer=OFFICER,
        system_metadata={
            "rpc_endpoints": ["https://eth-mainnet.g.alchemy.com/v2"],
            "block_range": "19000001-19000003",
        },
        generated_at=FIXED_TIME,
    )


def test_canonical_json_is_key_order_independent():
    """Two dicts with identical content must serialise -- and hash -- identically."""
    first = {"alpha": 1, "beta": {"y": 2, "x": 1}, "gamma": [3, 4]}
    second = {"gamma": [3, 4], "beta": {"x": 1, "y": 2}, "alpha": 1}

    assert canonical_json(first) == canonical_json(second)
    assert hashlib.sha256(canonical_json(first).encode()).hexdigest() == (
        hashlib.sha256(canonical_json(second).encode()).hexdigest()
    )


def test_canonical_json_serialises_datetimes_as_iso_utc():
    naive = {"seen_at": datetime(2026, 3, 14, 9, 30, 0)}
    aware = {"seen_at": datetime(2026, 3, 14, 9, 30, 0, tzinfo=UTC)}

    assert canonical_json(aware) == '{"seen_at":"2026-03-14T09:30:00Z"}'
    # A naive timestamp is read as UTC, so the two hash the same.
    assert canonical_json(naive) == canonical_json(aware)


def test_sha256_of_record_is_stable_and_payload_sensitive():
    record = _record(1)

    assert sha256_of_record(record) == sha256_of_record(_record(1))
    assert len(sha256_of_record(record)) == 64

    tampered = replace(record, payload={**record.payload, "value_usd": 9_999_999.0})
    assert sha256_of_record(tampered) != sha256_of_record(record)

    # Payload key order must not matter.
    reordered = replace(record, payload=dict(reversed(list(record.payload.items()))))
    assert sha256_of_record(reordered) == sha256_of_record(record)


def test_merkle_root_for_zero_one_two_three_and_four_records():
    hashes = [sha256_of_record(r) for r in _records(4)]

    assert merkle_root([]) == EMPTY_HASH
    assert merkle_root(hashes[:1]) == hashes[0]

    pair_01 = hashlib.sha256((hashes[0] + hashes[1]).encode()).hexdigest()
    assert merkle_root(hashes[:2]) == pair_01

    # Odd level: the last node is duplicated to pair cleanly.
    pair_22 = hashlib.sha256((hashes[2] + hashes[2]).encode()).hexdigest()
    assert merkle_root(hashes[:3]) == hashlib.sha256((pair_01 + pair_22).encode()).hexdigest()

    pair_23 = hashlib.sha256((hashes[2] + hashes[3]).encode()).hexdigest()
    assert merkle_root(hashes[:4]) == hashlib.sha256((pair_01 + pair_23).encode()).hexdigest()

    assert merkle_root(hashes[:3]) != merkle_root(hashes[:4])


def test_hash_chain_links_each_entry_to_its_predecessor():
    hashes = [sha256_of_record(r) for r in _records(3)]
    chain = build_hash_chain(hashes)

    assert build_hash_chain([]) == ()
    assert len(chain) == 3
    assert chain[0] == hashlib.sha256((EMPTY_HASH + hashes[0]).encode()).hexdigest()
    for i in range(1, 3):
        assert chain[i] == hashlib.sha256((chain[i - 1] + hashes[i]).encode()).hexdigest()

    # Changing an early link changes every link after it.
    altered = build_hash_chain([hashes[1], hashes[1], hashes[2]])
    assert altered[1] != chain[1]
    assert altered[2] != chain[2]


def test_build_certificate_populates_every_field_and_is_reproducible():
    records = _records(3)
    first = _certificate(records)
    second = _certificate(records)

    assert first == second, "identical evidence and timestamp must yield an identical certificate"
    assert first.certificate_id == f"TRX-S63-20260314-{first.merkle_root[:10].upper()}"
    assert first.generated_at == FIXED_TIME
    assert first.case_number == CASE_NUMBER
    assert first.investigating_officer == OFFICER
    assert first.record_count == 3
    assert first.record_hashes == tuple(sha256_of_record(r) for r in records)
    assert first.merkle_root == merkle_root(first.record_hashes)
    assert first.hash_chain == build_hash_chain(first.record_hashes)
    assert first.chain_tip == first.hash_chain[-1]
    assert first.system_metadata["rpc_endpoints"] == ["https://eth-mainnet.g.alchemy.com/v2"]
    assert first.system_metadata["extraction_timestamp_utc"] == "2026-03-14T09:30:00Z"
    assert first.system_metadata["hash_algorithm"] == "SHA-256"
    assert first.system_metadata["host"]
    assert "Section 63 of the Bharatiya Sakshya" in first.declaration
    assert first.merkle_root in first.declaration

    explicit = build_certificate(
        records,
        case_number=CASE_NUMBER,
        investigating_officer=OFFICER,
        certificate_id="TRX-S63-MANUAL-001",
        generated_at=FIXED_TIME,
    )
    assert explicit.certificate_id == "TRX-S63-MANUAL-001"


def test_verify_certificate_accepts_untouched_evidence():
    records = _records(4)
    certificate = _certificate(records)

    assert verify_certificate(certificate, records) == (True, [])
    # An empty record set still certifies and verifies.
    empty = _certificate([])
    assert empty.merkle_root == EMPTY_HASH
    assert empty.chain_tip == EMPTY_HASH
    assert verify_certificate(empty, []) == (True, [])


def test_tampering_with_one_record_names_that_record_index():
    records = _records(4)
    certificate = _certificate(records)

    tampered = list(records)
    tampered[2] = replace(
        records[2],
        payload={**records[2].payload, "value_usd": 0.01},
    )

    ok, problems = verify_certificate(certificate, tampered)

    assert ok is False
    assert any("record 2" in p and "hash mismatch" in p for p in problems)
    assert not any("record 0" in p or "record 1" in p for p in problems)
    assert any("merkle root mismatch" in p for p in problems)
    assert any("hash chain diverges from record 2" in p for p in problems)


def test_dropping_a_record_fails_verification():
    records = _records(4)
    certificate = _certificate(records)

    ok, problems = verify_certificate(certificate, records[:3])

    assert ok is False
    assert any("record count mismatch" in p for p in problems)
    assert any("record 3 is missing from the evidence supplied" in p for p in problems)
    assert any("merkle root mismatch" in p for p in problems)
    assert any("chain tip mismatch" in p for p in problems)


def test_reordering_records_fails_verification():
    records = _records(4)
    certificate = _certificate(records)

    swapped = [records[1], records[0], records[2], records[3]]
    ok, problems = verify_certificate(certificate, swapped)

    assert ok is False
    assert any("record 0" in p and "hash mismatch" in p for p in problems)
    assert any("record 1" in p and "hash mismatch" in p for p in problems)
    assert any("hash chain diverges from record 0" in p for p in problems)


def test_editing_the_certificate_declaration_is_detected():
    records = _records(2)
    certificate = _certificate(records)

    forged = replace(certificate, declaration="I declare whatever suits me.")
    ok, problems = verify_certificate(forged, records)

    assert ok is False
    assert any("declaration text does not match" in p for p in problems)


def test_html_carries_the_case_number_root_declaration_and_signature_block():
    records = _records(3)
    certificate = _certificate(records)
    document = generate_certificate_html(certificate)

    assert CASE_NUMBER in document
    assert certificate.certificate_id in document
    assert certificate.merkle_root in document
    assert certificate.chain_tip in document
    for record_hash in certificate.record_hashes:
        assert record_hash in document
    assert "SECTION 63 OF THE BHARATIYA SAKSHYA ADHINIYAM, 2023" in document
    assert "SECTION 65B OF THE INDIAN EVIDENCE ACT, 1872" in document
    assert "Signature of the Investigating Officer" in document
    assert OFFICER in document
    assert "Designation:" in document
    assert "Place:" in document
    # System environment metadata block.
    assert "System Environment Metadata" in document
    assert "rpc_endpoints" in document
    assert "2026-03-14T09:30:00Z" in document


def test_pdf_generation_returns_non_empty_pdf_bytes():
    certificate = _certificate(_records(3))
    pdf_bytes = generate_certificate_pdf(certificate)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000
