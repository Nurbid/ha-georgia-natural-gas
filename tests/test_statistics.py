"""Tests for GNG historical Home Assistant statistics."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from custom_components.georgia_natural_gas.models import parse_billing_csv
from custom_components.georgia_natural_gas.statistics import build_external_statistics


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

TZ = ZoneInfo("America/New_York")


def _record():
    """Return a parsed sample billing record."""
    return parse_billing_csv("\n".join((HEADER, ROW)))[0]


def _series(records):
    return build_external_statistics(
        records,
        entry_id="test-entry-id",
        timezone=TZ,
    )


def test_builds_energy_dashboard_gas_statistics() -> None:
    """Cumulative meter readings become CCF statistics with correct dates."""
    current = _record()
    previous = replace(
        current,
        bill_date=date(2026, 10, 3),
        bill_from_date=date(2026, 8, 25),
        bill_to_date=date(2026, 9, 24),
        meter_reading=8546,
    )

    metadata, stats = _series([previous, current])[0]

    assert metadata["statistic_id"].startswith(
        "georgia_natural_gas:gas_consumption_"
    )
    assert metadata["unit_of_measurement"] == "CCF"
    assert metadata["unit_class"] == "volume"
    assert metadata["has_sum"] is True
    assert len(stats) == 2
    assert stats[0]["state"] == 8546.0
    assert stats[0]["sum"] == 0.0
    assert stats[1]["state"] == 8561.0
    assert stats[1]["sum"] == 15.0
    # The supplied bill data reports 15.540 therms for this 15 CCF interval.
    assert current.gas_used_therms / Decimal(str(stats[1]["sum"])) == Decimal("1.036")
    assert stats[1]["start"].hour == 23
    assert stats[1]["start"].tzinfo is not None


def test_imports_therms_and_gas_charges_as_separate_series() -> None:
    """Therms and charges remain independently graphable billing metrics."""
    first = _record()
    second = replace(
        first,
        bill_date=date(2026, 12, 3),
        bill_from_date=date(2026, 10, 26),
        bill_to_date=date(2026, 11, 26),
        meter_reading=8577,
        gas_used_therms=Decimal("20.000"),
        gas_charges_excl_taxes=Decimal("80.00"),
    )

    series = _series([first, second])
    therms_metadata, therms = series[1]
    charges_metadata, charges = series[2]

    assert therms_metadata["unit_of_measurement"] == "thm"
    assert therms_metadata["unit_class"] is None
    assert therms[1]["sum"] == 35.54
    assert charges_metadata["unit_of_measurement"] == "USD"
    assert charges_metadata["unit_class"] is None
    assert charges[1]["sum"] == 158.25


def test_meter_reset_does_not_decrease_cumulative_usage() -> None:
    """A large meter-read drop is treated as a meter replacement/reset."""
    first = _record()
    second = replace(
        first,
        bill_date=date(2026, 12, 3),
        bill_from_date=date(2026, 10, 26),
        bill_to_date=date(2026, 11, 26),
        meter_reading=12,
    )

    _, stats = _series([first, second])[0]

    assert stats[0]["sum"] == 0
    assert stats[1]["sum"] == 12


def test_account_numbers_are_not_exposed_in_statistic_ids() -> None:
    """Statistic IDs are stable without embedding customer account numbers."""
    record = _record()

    metadata, _ = _series([record])[0]

    assert record.account_number not in metadata["statistic_id"]
    assert metadata["source"] == "georgia_natural_gas"
