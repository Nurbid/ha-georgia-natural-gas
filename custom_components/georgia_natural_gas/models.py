"""Data models and CSV parsing for Georgia Natural Gas billing records."""

import csv
import io
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class BillingRecord:
    """One GNG billing-period record."""

    customer_name: str
    address: str
    account_number: str
    bill_date: date
    bill_from_date: date
    bill_to_date: date
    days_of_service: int
    meter_reading: int
    gas_used_therms: Decimal
    heating_degree_days: Decimal
    average_temperature: Decimal
    sum_of_payments: Decimal
    balance_forward: Decimal
    gas_charges_excl_taxes: Decimal
    other_charges: Decimal
    promotional_discounts: Decimal
    taxes: Decimal
    budget_billing_amount: Decimal
    guaranteed_billing_amount: Decimal
    amount_due: Decimal


_REQUIRED_COLUMNS = (
    "Customer Name",
    "Address",
    "Account Number",
    "Bill Date",
    "Bill From Date",
    "Bill To Date",
    "Days Of Service",
    "Meter Reading",
    "Gas Used (Therms)",
    "Heating Degree Days",
    "Average Temperature",
    "Sum Of Payments",
    "Balance Forward",
    "Gas Charges (Excl. Taxes)",
    "Other Charges",
    "Promotional Discounts",
    "Taxes",
    "Budget Billing Amount",
    "Guaranteed Billing Amount",
    "Amount Due",
)


def parse_billing_csv(csv_data: str) -> list[BillingRecord]:
    """Parse GNG billing CSV into validated BillingRecord objects."""

    if not isinstance(csv_data, str):
        raise TypeError("Billing export must be text.")

    reader = csv.DictReader(io.StringIO(csv_data.lstrip("\ufeff")))

    if reader.fieldnames is None:
        raise ValueError("Billing export is missing its header row.")

    missing_columns = set(_REQUIRED_COLUMNS) - set(reader.fieldnames)
    if missing_columns:
        raise ValueError(
            "Billing export is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    records: list[BillingRecord] = []

    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(f"Billing export row {row_number} has extra columns.")

        def value(
            field: str,
            *,
            _row=row,
            _row_number=row_number,
        ) -> str:
            raw_value = _row.get(field)
            if not isinstance(raw_value, str) or not raw_value.strip():
                raise ValueError(
                    f"Billing export row {_row_number} has an empty {field} value."
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
                    f"Billing export row {_row_number} has an invalid {field} date."
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
                    f"Billing export row {_row_number} has an invalid {field} value."
                ) from None
            if not result.is_finite():
                raise ValueError(
                    f"Billing export row {_row_number} has a non-finite {field} value."
                )
            return result

        def as_integer(
            field: str,
            *,
            _value=value,
            _row_number=row_number,
        ) -> int:
            try:
                return int(_value(field))
            except ValueError:
                raise ValueError(
                    f"Billing export row {_row_number} has an invalid {field} value."
                ) from None

        records.append(
            BillingRecord(
                customer_name=value("Customer Name"),
                address=value("Address"),
                account_number=value("Account Number"),
                bill_date=as_date("Bill Date"),
                bill_from_date=as_date("Bill From Date"),
                bill_to_date=as_date("Bill To Date"),
                days_of_service=as_integer("Days Of Service"),
                meter_reading=as_integer("Meter Reading"),
                gas_used_therms=as_decimal("Gas Used (Therms)"),
                heating_degree_days=as_decimal("Heating Degree Days"),
                average_temperature=as_decimal("Average Temperature"),
                sum_of_payments=as_decimal("Sum Of Payments"),
                balance_forward=as_decimal("Balance Forward"),
                gas_charges_excl_taxes=as_decimal("Gas Charges (Excl. Taxes)"),
                other_charges=as_decimal("Other Charges"),
                promotional_discounts=as_decimal("Promotional Discounts"),
                taxes=as_decimal("Taxes"),
                budget_billing_amount=as_decimal("Budget Billing Amount"),
                guaranteed_billing_amount=as_decimal("Guaranteed Billing Amount"),
                amount_due=as_decimal("Amount Due"),
            )
        )

    return records


def serialize_billing_record(record: BillingRecord) -> dict[str, str | int]:
    """Convert a BillingRecord into JSON-compatible data."""

    data = asdict(record)

    for key, value in data.items():
        if isinstance(value, (date, Decimal)):
            data[key] = str(value)

    return data


def deserialize_billing_record(data: dict[str, str | int]) -> BillingRecord:
    """Reconstruct a BillingRecord from stored data."""

    return BillingRecord(
        customer_name=str(data["customer_name"]),
        address=str(data["address"]),
        account_number=str(data["account_number"]),
        bill_date=date.fromisoformat(str(data["bill_date"])),
        bill_from_date=date.fromisoformat(str(data["bill_from_date"])),
        bill_to_date=date.fromisoformat(str(data["bill_to_date"])),
        days_of_service=int(data["days_of_service"]),
        meter_reading=int(data["meter_reading"]),
        gas_used_therms=Decimal(str(data["gas_used_therms"])),
        heating_degree_days=Decimal(str(data["heating_degree_days"])),
        average_temperature=Decimal(str(data["average_temperature"])),
        sum_of_payments=Decimal(str(data["sum_of_payments"])),
        balance_forward=Decimal(str(data["balance_forward"])),
        gas_charges_excl_taxes=Decimal(str(data["gas_charges_excl_taxes"])),
        other_charges=Decimal(str(data["other_charges"])),
        promotional_discounts=Decimal(str(data["promotional_discounts"])),
        taxes=Decimal(str(data["taxes"])),
        budget_billing_amount=Decimal(str(data["budget_billing_amount"])),
        guaranteed_billing_amount=Decimal(str(data["guaranteed_billing_amount"])),
        amount_due=Decimal(str(data["amount_due"])),
    )


def merge_billing_records(
    existing: list[BillingRecord],
    incoming: list[BillingRecord],
) -> list[BillingRecord]:
    """Merge billing history, preferring the latest incoming records."""

    merged = {
        (
            record.account_number,
            record.bill_from_date,
            record.bill_to_date,
        ): record
        for record in existing
    }

    for record in incoming:
        key = (
            record.account_number,
            record.bill_from_date,
            record.bill_to_date,
        )
        merged[key] = record

    return sorted(
        merged.values(),
        key=lambda record: (record.bill_date, record.account_number),
    )
