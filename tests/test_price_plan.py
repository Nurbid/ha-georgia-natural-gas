"""Tests for Price Plan parsing and actual service-cost reconciliation."""

from datetime import date
from decimal import Decimal

from custom_components.gng.models import parse_billing_csv
from custom_components.gng.price_plan import (
    build_cost_by_bill_date,
    detect_plan_capability,
    detailed_component_cost,
    parse_price_plan_csv,
    resolve_actual_service_cost,
)
from custom_components.gng.statistics import (
    build_daily_cost_statistics,
)
from zoneinfo import ZoneInfo


BILLING_HEADER = (
    "Customer Name,Address,Account Number,Bill Date,Bill From Date,"
    "Bill To Date,Days Of Service,Meter Reading,Gas Used (Therms),"
    "Heating Degree Days,Average Temperature,Sum Of Payments,"
    "Balance Forward,Gas Charges (Excl. Taxes),Other Charges,"
    "Promotional Discounts,Taxes,Budget Billing Amount,"
    "Guaranteed Billing Amount,Amount Due"
)

BILLING_ROW = (
    "Sample Customer,1 Example Road,0000000000000000,2026/11/03,"
    "2026/09/24,2026/10/26,32,8561,15.540,48.0,68.0,155.58,"
    "0.00,78.25,0.00,0.00,6.96,155.58,0.00,155.58"
)

PRICE_PLAN_CSV = (
    "Bill Date,Budget Billing Installment Amount,Actual Bill Charges,"
    "Monthly Budget Billing Variance,"
    "Total Budget Billing Variance after this Bill is Paid\n"
    "2026/11/03,155.58,85.21,-70.37,653.01\n"
)

TZ = ZoneInfo("America/New_York")


def test_parse_price_plan_csv() -> None:
    """Price Plan spreadsheet columns map to typed period records."""

    records = parse_price_plan_csv(PRICE_PLAN_CSV)

    assert len(records) == 1
    assert records[0].bill_date == date(2026, 11, 3)
    assert records[0].installment_amount == Decimal("155.58")
    assert records[0].actual_bill_charges == Decimal("85.21")
    assert records[0].monthly_variance == Decimal("-70.37")
    assert records[0].accumulated_variance == Decimal("653.01")


def test_resolve_prefers_price_plan_actual() -> None:
    """Energy cost uses Price Plan actual charges when present."""

    billing = parse_billing_csv("\n".join((BILLING_HEADER, BILLING_ROW)))[0]
    price_plan = parse_price_plan_csv(PRICE_PLAN_CSV)[0]

    amount, source = resolve_actual_service_cost(billing, price_plan)

    assert amount == Decimal("85.21")
    assert source == "price_plan"
    assert detailed_component_cost(billing) == Decimal("85.21")


def test_resolve_falls_back_to_detailed_components() -> None:
    """Non-budget accounts use Detailed Gas+Tax+Other(+Promo)."""

    billing = parse_billing_csv("\n".join((BILLING_HEADER, BILLING_ROW)))[0]

    amount, source = resolve_actual_service_cost(billing, None)

    assert amount == Decimal("85.21")
    assert source == "detailed_components"


def test_detect_plan_capability() -> None:
    """Capability reflects whether Price Plan rows were retrieved."""

    assert (
        detect_plan_capability([], fetch_succeeded=True) == "none"
    )
    assert (
        detect_plan_capability(
            parse_price_plan_csv(PRICE_PLAN_CSV),
            fetch_succeeded=True,
        )
        == "budget_billing"
    )
    assert (
        detect_plan_capability(None, fetch_succeeded=False) == "unknown"
    )


def test_daily_cost_statistics_preserve_actual_total() -> None:
    """Daily cost estimates sum exactly to reconciled actual charges."""

    billing = parse_billing_csv("\n".join((BILLING_HEADER, BILLING_ROW)))[0]
    costs = {
        bill_date: amount
        for bill_date, (amount, _source) in build_cost_by_bill_date(
            [billing],
            parse_price_plan_csv(PRICE_PLAN_CSV),
        ).items()
    }

    statistics = build_daily_cost_statistics(
        [billing],
        costs,
        timezone=TZ,
        as_of_date=date(2026, 10, 27),
    )

    assert len(statistics) == 32
    assert round(statistics[-1]["sum"], 2) == 85.21
    assert round(statistics[-1]["state"], 2) == 85.21
