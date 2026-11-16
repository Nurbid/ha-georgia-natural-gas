"""Price Plan (EppHistory) models and actual service-cost reconciliation."""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from .const import (
    PLAN_CAPABILITY_BUDGET_BILLING,
    PLAN_CAPABILITY_NONE,
    PLAN_CAPABILITY_UNKNOWN,
)
from .models import BillingRecord

_LOGGER = logging.getLogger(__name__)

_REQUIRED_COLUMNS = (
    "Bill Date",
    "Budget Billing Installment Amount",
    "Actual Bill Charges",
    "Monthly Budget Billing Variance",
    "Total Budget Billing Variance after this Bill is Paid",
)


@dataclass(frozen=True)
class PricePlanPeriod:
    """One GNG Price Plan / budget-billing history row."""

    bill_date: date
    installment_amount: Decimal
    actual_bill_charges: Decimal
    monthly_variance: Decimal
    accumulated_variance: Decimal


def parse_price_plan_csv(csv_data: str) -> list[PricePlanPeriod]:
    """Parse EppHistory spreadsheet CSV into PricePlanPeriod objects."""

    if not isinstance(csv_data, str):
        raise TypeError("Price Plan export must be text.")

    reader = csv.DictReader(io.StringIO(csv_data.lstrip("\ufeff")))

    if reader.fieldnames is None:
        raise ValueError("Price Plan export is missing its header row.")

    missing_columns = set(_REQUIRED_COLUMNS) - set(reader.fieldnames)
    if missing_columns:
        raise ValueError(
            "Price Plan export is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    records: list[PricePlanPeriod] = []

    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(
                f"Price Plan export row {row_number} has extra columns."
            )

        def value(
            field: str,
            *,
            _row=row,
            _row_number=row_number,
        ) -> str:
            raw_value = _row.get(field)
            if not isinstance(raw_value, str) or not raw_value.strip():
                raise ValueError(
                    f"Price Plan export row {_row_number} has an empty "
                    f"{field} value."
                )
            return raw_value.strip()

        def as_date(
            field: str,
            *,
            _value=value,
            _row_number=row_number,
        ) -> date:
            try:
                return date.fromisoformat(_value(field).replace("/", "-"))
            except ValueError:
                raise ValueError(
                    f"Price Plan export row {_row_number} has an invalid "
                    f"{field} date."
                ) from None

        def as_decimal(
            field: str,
            *,
            _value=value,
            _row_number=row_number,
        ) -> Decimal:
            try:
                result = Decimal(_value(field))
            except InvalidOperation:
                raise ValueError(
                    f"Price Plan export row {_row_number} has an invalid "
                    f"{field} value."
                ) from None
            if not result.is_finite():
                raise ValueError(
                    f"Price Plan export row {_row_number} has a non-finite "
                    f"{field} value."
                )
            return result

        records.append(
            PricePlanPeriod(
                bill_date=as_date("Bill Date"),
                installment_amount=as_decimal(
                    "Budget Billing Installment Amount"
                ),
                actual_bill_charges=as_decimal("Actual Bill Charges"),
                monthly_variance=as_decimal(
                    "Monthly Budget Billing Variance"
                ),
                accumulated_variance=as_decimal(
                    "Total Budget Billing Variance after this Bill is Paid"
                ),
            )
        )

    return records


def serialize_price_plan_period(record: PricePlanPeriod) -> dict[str, str]:
    """Convert a PricePlanPeriod into JSON-compatible data."""

    data = asdict(record)
    for key, value in data.items():
        if isinstance(value, (date, Decimal)):
            data[key] = str(value)
    return data


def deserialize_price_plan_period(
    data: dict[str, str],
) -> PricePlanPeriod:
    """Reconstruct a PricePlanPeriod from stored data."""

    return PricePlanPeriod(
        bill_date=date.fromisoformat(str(data["bill_date"])),
        installment_amount=Decimal(str(data["installment_amount"])),
        actual_bill_charges=Decimal(str(data["actual_bill_charges"])),
        monthly_variance=Decimal(str(data["monthly_variance"])),
        accumulated_variance=Decimal(str(data["accumulated_variance"])),
    )


def merge_price_plan_periods(
    existing: list[PricePlanPeriod],
    incoming: list[PricePlanPeriod],
) -> list[PricePlanPeriod]:
    """Merge Price Plan history, preferring incoming rows for the same bill date."""

    merged = {record.bill_date: record for record in existing}
    for record in incoming:
        merged[record.bill_date] = record
    return sorted(merged.values(), key=lambda record: record.bill_date)


def detailed_component_cost(record: BillingRecord) -> Decimal:
    """Fallback actual cost from DownloadData Detailed components."""

    return (
        record.gas_charges_excl_taxes
        + record.taxes
        + record.other_charges
        + record.promotional_discounts
    )


def detect_plan_capability(
    price_plan_records: list[PricePlanPeriod] | None,
    *,
    fetch_succeeded: bool,
) -> str:
    """Classify pricing-plan support for the selected account."""

    if not fetch_succeeded:
        return PLAN_CAPABILITY_UNKNOWN
    if price_plan_records:
        return PLAN_CAPABILITY_BUDGET_BILLING
    return PLAN_CAPABILITY_NONE


def resolve_actual_service_cost(
    billing: BillingRecord,
    price_plan: PricePlanPeriod | None,
) -> tuple[Decimal, str]:
    """Return (actual_service_cost, source) for Energy total-cost tracking.

    Prefer Price Plan Actual Bill Charges. Fall back to Detailed components.
    """

    component_cost = detailed_component_cost(billing)

    if price_plan is None:
        return component_cost, "detailed_components"

    if component_cost != price_plan.actual_bill_charges:
        _LOGGER.debug(
            "Price Plan actual charges differ from Detailed components "
            "for bill_date=%s (delta=%s).",
            billing.bill_date.isoformat(),
            price_plan.actual_bill_charges - component_cost,
        )

    return price_plan.actual_bill_charges, "price_plan"


def build_cost_by_bill_date(
    billing_records: list[BillingRecord],
    price_plan_records: list[PricePlanPeriod],
) -> dict[date, tuple[Decimal, str]]:
    """Map each billing period's bill_date to (actual cost, source)."""

    price_by_date = {
        record.bill_date: record for record in price_plan_records
    }
    costs: dict[date, tuple[Decimal, str]] = {}

    for billing in billing_records:
        costs[billing.bill_date] = resolve_actual_service_cost(
            billing,
            price_by_date.get(billing.bill_date),
        )

    return costs


def latest_period_service_cost(
    billing_records: list[BillingRecord],
    price_plan_records: list[PricePlanPeriod],
) -> tuple[Decimal, str] | None:
    """Return (amount, source) for the latest bill's actual service cost.

    This is the dashboard total for Gas+Tax+Other+Promo (or Price Plan
    Actual Bill Charges when that export is available).
    """

    if not billing_records:
        return None

    costs = build_cost_by_bill_date(billing_records, price_plan_records)
    latest = max(billing_records, key=lambda record: record.bill_date)
    return costs.get(latest.bill_date)
