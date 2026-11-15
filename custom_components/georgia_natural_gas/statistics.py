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

        address = ordered[-1].address
        suffix = (entry_id, account_number)
        result.extend(
            [
                (
                    _metadata(
                        "gas_consumption",
                        suffix,
                        f"Georgia Natural Gas • Monthly consumption • {address}",
                        "CCF",
                        "volume",
                    ),
                    _build_meter_statistics(ordered, timezone),
                ),
                (
                    _metadata(
                        "gas_usage_therms",
                        suffix,
                        f"Georgia Natural Gas • Therm usage • {address}",
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
                        f"Georgia Natural Gas • Gas charges • {address}",
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
            cumulative_usage = max(Decimal(0), cumulative_usage + difference)

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


def build_daily_consumption_statistics(
    records: Iterable[BillingRecord],
    *,
    timezone: tzinfo,
    as_of_date: date,
) -> list[dict]:
    """Build estimated daily cumulative therm statistics from billing totals.

    Each bill's actual therm total is distributed evenly across its service
    days. After the latest bill period, the latest daily average is projected
    through yesterday. The current day is intentionally left incomplete.
    """
    records_by_account: dict[str, list[BillingRecord]] = defaultdict(list)
    for record in records:
        records_by_account[record.account_number].append(record)

    if not records_by_account:
        return []

    # A config entry represents one selected service account. Never combine
    # records from multiple accounts if the portal export changes behavior.
    account_records = max(
        records_by_account.values(),
        key=lambda items: max(record.bill_date for record in items),
    )
    ordered = sorted(
        account_records,
        key=lambda record: (record.bill_to_date, record.bill_date),
    )
    records_by_end_date = {record.bill_to_date: record for record in ordered}
    ordered = [
        records_by_end_date[end_date]
        for end_date in sorted(records_by_end_date)
    ]

    yesterday = date.fromordinal(as_of_date.toordinal() - 1)
    daily_usage: dict[date, Decimal] = {}

    for record in ordered:
        period_days = (record.bill_to_date - record.bill_from_date).days
        if period_days <= 0 or period_days != record.days_of_service:
            raise ValueError("GNG billing period dates do not match service days.")

        daily_usage_value = record.gas_used_therms / Decimal(period_days)
        for day_number in range(1, period_days + 1):
            usage_date = date.fromordinal(
                record.bill_from_date.toordinal() + day_number
            )
            if usage_date > yesterday:
                continue
            if usage_date in daily_usage:
                raise ValueError("GNG billing periods contain overlapping dates.")
            daily_usage[usage_date] = daily_usage_value

    if ordered:
        latest = ordered[-1]
        period_days = (latest.bill_to_date - latest.bill_from_date).days
        if period_days > 0:
            estimated_daily_usage = (
                latest.gas_used_therms / Decimal(period_days)
            )
            first_estimated_day = date.fromordinal(
                latest.bill_to_date.toordinal() + 1
            )
            for day_number in range(
                max(0, (yesterday - first_estimated_day).days + 1)
            ):
                usage_date = date.fromordinal(
                    first_estimated_day.toordinal() + day_number
                )
                daily_usage.setdefault(usage_date, estimated_daily_usage)

    statistics: list[dict] = []
    cumulative_usage = Decimal(0)

    for usage_date, daily_amount in sorted(daily_usage.items()):
        cumulative_usage += daily_amount
        statistics.append(
            {
                "start": _billing_timestamp(usage_date, timezone),
                "state": float(cumulative_usage),
                "sum": float(cumulative_usage),
            }
        )

    return statistics
