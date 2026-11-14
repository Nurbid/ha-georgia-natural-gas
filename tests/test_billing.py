"""Tests for GNG billing record parsing, persistence, and validation."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from custom_components.georgia_natural_gas.api import validate_billing_records
from custom_components.georgia_natural_gas.models import (
    deserialize_billing_record,
    merge_billing_records,
    parse_billing_csv,
    serialize_billing_record,
)

HEADER = (
    "Customer Name,Address,Account Number,Bill Date,Bill From Date,"
    "Bill To Date,Days Of Service,Meter Reading,Gas Used (Therms),"
    "Heating Degree Days,Average Temperature,Sum Of Payments,"
    "Balance Forward,Gas Charges (Excl. Taxes),Other Charges,"
    "Promotional Discounts,Taxes,Budget Billing Amount,"
    "Guaranteed Billing Amount,Amount Due"
)

ROW = (
    "Sample Customer,1 Example Road,0000000000000000,2026/11/03,"
    "2026/09/24,2026/10/26,32,8561,15.540,48.0,68.0,155.58,"
    "0.00,78.25,0.00,0.00,6.96,155.58,0.00,155.58"
)


def parse_rows(*rows: str) -> list:
    """Parse one or more test rows."""
    return parse_billing_csv("\n".join((HEADER, *rows)))


def test_parse_billing_csv() -> None:
    """Parse GNG dates, decimals, and integer fields."""
    record = parse_rows(ROW)[0]

    assert record.bill_date == date(2026, 11, 3)
    assert record.bill_from_date == date(2026, 9, 24)
    assert record.bill_to_date == date(2026, 10, 26)
    assert record.days_of_service == 32
    assert record.gas_used_therms == Decimal("15.540")
    assert record.amount_due == Decimal("155.58")


def test_parse_empty_export() -> None:
    """An export with headers and no rows returns an empty list."""
    assert parse_billing_csv(HEADER) == []


def test_reject_missing_required_column() -> None:
    """Reject a CSV whose header is missing a required field."""
    incomplete_header = HEADER.replace(",Taxes,", ",")
    with pytest.raises(ValueError, match="Taxes"):
        parse_billing_csv(incomplete_header + "\n" + ROW)


def test_reject_empty_required_value() -> None:
    """Reject blank values instead of creating incomplete records."""
    row = ROW.replace(",15.540,", ",,")
    with pytest.raises(ValueError, match="Gas Used"):
        parse_rows(row)


def test_reject_non_finite_decimal() -> None:
    """Reject NaN and infinity values that Home Assistant cannot represent."""
    row = ROW.replace(",15.540,", ",NaN,")
    with pytest.raises(ValueError, match="non-finite"):
        parse_rows(row)


def test_serialize_deserialize_round_trip() -> None:
    """Persisted billing records can be reconstructed without data loss."""
    record = parse_rows(ROW)[0]

    assert deserialize_billing_record(serialize_billing_record(record)) == record


def test_merge_prefers_incoming_record_for_same_period() -> None:
    """A refreshed record replaces the stored version of the same period."""
    existing = parse_rows(ROW)[0]
    incoming = replace(existing, gas_used_therms=Decimal("16.250"))

    merged = merge_billing_records([existing], [incoming])

    assert merged == [incoming]


def test_validate_contiguous_periods() -> None:
    """Contiguous billing periods pass validation."""
    first = parse_rows(ROW)[0]
    second_row = ROW.replace(
        "2026/11/03,2026/09/24,2026/10/26,32,",
        "2026/12/03,2026/10/26,2026/11/26,31,",
    )
    second = parse_rows(second_row)[0]

    assert validate_billing_records([first, second]) == []


def test_validation_reports_gap_without_account_number() -> None:
    """Continuity errors must not expose customer account identifiers."""
    first = parse_rows(ROW)[0]
    gap_row = ROW.replace(
        "2026/11/03,2026/09/24,2026/10/26,32,",
        "2026/12/03,2026/10/27,2026/11/27,31,",
    )
    second = parse_rows(gap_row)[0]

    issues = validate_billing_records([first, second])

    assert len(issues) == 1
    assert "Gap in billing periods" in issues[0]
    assert first.account_number not in issues[0]


def test_validation_reports_duplicate_period() -> None:
    """Duplicate billing periods are detected."""
    record = parse_rows(ROW)[0]

    issues = validate_billing_records([record, record])

    assert any("Duplicate billing period" in issue for issue in issues)
