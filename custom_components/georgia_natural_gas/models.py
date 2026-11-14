
import csv
import io

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal


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


def parse_billing_csv(csv_data):
    """Parse GNG billing CSV into BillingRecord objects."""

    records = []

    reader = csv.DictReader(io.StringIO(csv_data.lstrip("\ufeff")))

    for row in reader:
        def value(field):
            return row[field].strip()

        def as_date(field):
            return date.fromisoformat(value(field).replace("/", "-"))

        def as_decimal(field):
            return Decimal(value(field))

        records.append(
            BillingRecord(
                customer_name=value("Customer Name"),
                address=value("Address"),
                account_number=value("Account Number"),
                bill_date=as_date("Bill Date"),
                bill_from_date=as_date("Bill From Date"),
                bill_to_date=as_date("Bill To Date"),
                days_of_service=int(value("Days Of Service")),
                meter_reading=int(value("Meter Reading")),
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


def serialize_billing_record(record):
    """Convert a BillingRecord into JSON-compatible data."""

    data = asdict(record)

    for key, value in data.items():
        if isinstance(value, (date, Decimal)):
            data[key] = str(value)

    return data


def deserialize_billing_record(data):
	"""Reconstruct a BillingRecord from stored data."""

	return BillingRecord(
		customer_name=data["customer_name"],
		address=data["address"],
		account_number=data["account_number"],
		bill_date=date.fromisoformat(data["bill_date"]),
		bill_from_date=date.fromisoformat(data["bill_from_date"]),
		bill_to_date=date.fromisoformat(data["bill_to_date"]),
		days_of_service=int(data["days_of_service"]),
		meter_reading=int(data["meter_reading"]),
		gas_used_therms=Decimal(data["gas_used_therms"]),
		heating_degree_days=Decimal(data["heating_degree_days"]),
		average_temperature=Decimal(data["average_temperature"]),
		sum_of_payments=Decimal(data["sum_of_payments"]),
		balance_forward=Decimal(data["balance_forward"]),
		gas_charges_excl_taxes=Decimal(data["gas_charges_excl_taxes"]),
		other_charges=Decimal(data["other_charges"]),
		promotional_discounts=Decimal(data["promotional_discounts"]),
		taxes=Decimal(data["taxes"]),
		budget_billing_amount=Decimal(data["budget_billing_amount"]),
		guaranteed_billing_amount=Decimal(data["guaranteed_billing_amount"]),
		amount_due=Decimal(data["amount_due"]),
	)


def merge_billing_records(existing, incoming):
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
		key=lambda record: (
			record.bill_date,
			record.account_number,
		),
	)