"""Historical statistics for Home Assistant's Energy dashboard."""

from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import date, datetime, time, tzinfo
from decimal import Decimal
from hashlib import sha256

from .const import DOMAIN
from .models import BillingRecord


def _statistic_id(metric: str, entry_id: str, account_number: str) -> str:
    """Build a stable statistic ID without exposing the account number."""
    account_hash = sha256(account_number.encode()).hexdigest()[:8]
    entry_slug = entry_id.replace("-", "_")
    return f"{DOMAIN}:{metric}_{entry_slug}_{account_hash}"


def _billing_timestamp(value: date, timezone: tzinfo) -> datetime:
    """Place billing-period totals at the end of the reported service date."""
    return datetime.combine(value, time(hour=23), tzinfo=timezone)


def build_external_statistics(
    records: Iterable[BillingRecord],
    *,
    entry_id: str,
    timezone: tzinfo,
) -> list[tuple[dict, list[dict]]]:
    """Build idempotent cumulative statistics from GNG billing records.

    GNG's export provides a cumulative meter reading and period therms, but
    not daily or hourly consumption. Meter readings are treated as CCF
    (hundreds of cubic feet), as described in GNG's bill explanation.
    """
    records_by_account: dict[str, list[BillingRecord]] = defaultdict(list)
    for record in records:
        records_by_account[record.account_number].append(record)

    result: list[tuple[dict, list[dict]]] = []

    for account_number, account_records in records_by_account.items():
        ordered = sorted(
            account_records,
            key=lambda record: (record.bill_to_date, record.bill_date),
        )

        # Prefer the latest bill if the portal returns duplicate end dates.
        records_by_end_date = {
            record.bill_to_date: record for record in ordered
        }
        ordered = [
            records_by_end_date[end_date]
            for end_date in sorted(records_by_end_date)
        ]

        suffix = (entry_id, account_number)
        result.extend(
            [
                (
                    _metadata(
                        "gas_consumption",
                        suffix,
                        "Georgia Natural Gas consumption",
                        "CCF",
                        "volume",
                    ),
                    _build_meter_statistics(ordered, timezone),
                ),
                (
                    _metadata(
                        "gas_usage_therms",
                        suffix,
                        "Georgia Natural Gas usage (therms)",
                        "thm",
                        None,
                    ),
                    _build_increment_statistics(
                        ordered,
                        timezone,
                        lambda record: record.gas_used_therms,
                    ),
                ),
                (
                    _metadata(
                        "gas_charges_usd",
                        suffix,
                        "Georgia Natural Gas gas charges",
                        "USD",
                        None,
                    ),
                    _build_increment_statistics(
                        ordered,
                        timezone,
                        lambda record: record.gas_charges_excl_taxes,
                    ),
                ),
            ]
        )

    return [
        (metadata, statistics)
        for metadata, statistics in result
        if statistics
    ]


def _metadata(
    metric: str,
    suffix: tuple[str, str],
    name: str,
    unit: str,
    unit_class: str | None,
) -> dict:
    """Return Home Assistant external-statistics metadata."""
    entry_id, account_number = suffix
    return {
        "statistic_id": _statistic_id(metric, entry_id, account_number),
        "source": DOMAIN,
        "name": name,
        "unit_of_measurement": unit,
        "unit_class": unit_class,
        "has_sum": True,
        "mean_type": 0,
    }


def _build_meter_statistics(
    records: list[BillingRecord],
    timezone: tzinfo,
) -> list[dict]:
    """Build cumulative CCF statistics from the meter's actual readings."""
    statistics: list[dict] = []
    previous_reading: Decimal | None = None
    cumulative_usage = Decimal(0)

    for record in records:
        reading = Decimal(record.meter_reading)

        if previous_reading is not None:
            difference = reading - previous_reading
            # A substantial decrease indicates a meter replacement/reset.
            if difference < 0 and reading < previous_reading * Decimal("0.9"):
                difference = reading
            cumulative_usage += difference

        statistics.append(
            {
                "start": _billing_timestamp(record.bill_to_date, timezone),
                "state": float(reading),
                "sum": float(cumulative_usage),
            }
        )
        previous_reading = reading

    return statistics


def _build_increment_statistics(
    records: list[BillingRecord],
    timezone: tzinfo,
    value_fn: Callable[[BillingRecord], Decimal],
) -> list[dict]:
    """Build cumulative statistics from billing-period amounts."""
    statistics: list[dict] = []
    cumulative = Decimal(0)

    for record in records:
        cumulative += value_fn(record)
        statistics.append(
            {
                "start": _billing_timestamp(record.bill_to_date, timezone),
                "state": float(cumulative),
                "sum": float(cumulative),
            }
        )

    return statistics
