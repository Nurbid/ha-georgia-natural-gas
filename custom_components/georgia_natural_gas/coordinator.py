"""Data coordinator for Georgia Natural Gas."""

import calendar
import csv
import logging
from datetime import UTC, date, timedelta
from decimal import Decimal

import aiohttp
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import (
    GeorgiaNaturalGasClient,
    GNGAuthenticationError,
    GNGError,
    validate_billing_records,
)
from .const import (
    CONF_ACCOUNT_NUMBER,
    CONF_ACCOUNT_SELECTION,
    CONF_SERVICE_ADDRESS,
    CONF_UPDATE_INTERVAL_DAYS,
    DEFAULT_ACCOUNT_SELECTION,
    DEFAULT_UPDATE_INTERVAL_DAYS,
    DOMAIN,
    MAX_UPDATE_INTERVAL_DAYS,
    MIN_UPDATE_INTERVAL_DAYS,
    PLAN_CAPABILITY_BUDGET_BILLING,
    PLAN_CAPABILITY_NONE,
    PLAN_CAPABILITY_UNKNOWN,
    STORAGE_VERSION,
)
from .identity import account_display_name
from .models import (
    deserialize_billing_record,
    merge_billing_records,
    parse_billing_csv,
    serialize_billing_record,
)
from .price_plan import (
    build_cost_by_bill_date,
    deserialize_price_plan_period,
    detect_plan_capability,
    merge_price_plan_periods,
    parse_price_plan_csv,
    serialize_price_plan_period,
)
from .statistics import (
    build_daily_consumption_statistics,
    build_daily_cost_statistics,
    build_external_service_cost_statistics,
    build_external_statistics,
)

_LOGGER = logging.getLogger(__name__)


def _subtract_months(value, months):
    """Subtract calendar months while preserving a valid day."""

    month_index = value.month - 1 - months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])

    return value.replace(year=year, month=month, day=day)


def _iso_utc_date(value) -> str:
    """Format a datetime as the GNG DownloadData ISO UTC string."""

    return (
        value.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def update_interval_from_options(options) -> timedelta:
    """Resolve the configured update interval with sane bounds."""

    raw = options.get(
        CONF_UPDATE_INTERVAL_DAYS,
        DEFAULT_UPDATE_INTERVAL_DAYS,
    )
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = DEFAULT_UPDATE_INTERVAL_DAYS

    days = max(
        MIN_UPDATE_INTERVAL_DAYS,
        min(MAX_UPDATE_INTERVAL_DAYS, days),
    )
    return timedelta(days=days)


class GeorgiaNaturalGasCoordinator(DataUpdateCoordinator):
    """Manage GNG billing data and historical storage."""

    def __init__(self, hass, entry, session):
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval_from_options(entry.options),
            # The daily estimate advances even when GNG's billing records do not change.
            always_update=True,
        )

        self.hass = hass
        self.config_entry = entry
        self.entry_id = entry.entry_id
        self.client = GeorgiaNaturalGasClient(
            session,
            entry.data["username"],
            entry.data["password"],
        )
        self.account_selection = entry.options.get(
            CONF_ACCOUNT_SELECTION,
            DEFAULT_ACCOUNT_SELECTION,
        )
        self.account_number = entry.data.get(CONF_ACCOUNT_NUMBER, "")
        self.service_address = entry.data.get(CONF_SERVICE_ADDRESS, "")
        self.account_display_name = (
            account_display_name(self.account_number, self.service_address)
            if self.account_number
            else "Georgia Natural Gas"
        )

        # Keep the original storage key for the verified default selection so
        # existing users retain their billing history without a schema migration.
        storage_key = f"{DOMAIN}_{entry.entry_id}"
        if self.account_selection != DEFAULT_ACCOUNT_SELECTION:
            storage_key = f"{storage_key}_{self.account_selection}"

        self.store = Store(
            hass,
            STORAGE_VERSION,
            storage_key,
        )

        self.records = []
        self.price_plan_records = []
        self.plan_capability = PLAN_CAPABILITY_UNKNOWN
        self.gas_consumption_entity_id = None
        self.gas_service_cost_entity_id = None

    def cost_amounts_by_bill_date(self) -> dict[date, Decimal]:
        """Return reconciled actual service costs keyed by bill date."""

        return {
            bill_date: amount
            for bill_date, (amount, _source) in build_cost_by_bill_date(
                self.records,
                self.price_plan_records,
            ).items()
        }

    def cost_sources_by_bill_date(self) -> dict[date, str]:
        """Return cost-source labels keyed by bill date."""

        return {
            bill_date: source
            for bill_date, (_amount, source) in build_cost_by_bill_date(
                self.records,
                self.price_plan_records,
            ).items()
        }

    def import_gas_consumption_statistics(self, entity_id: str) -> None:
        """Import daily estimates under the Energy sensor's native statistic ID."""

        if not self.records:
            return

        self.gas_consumption_entity_id = entity_id
        try:
            statistics = build_daily_consumption_statistics(
                self.records,
                timezone=dt_util.get_default_time_zone(),
                as_of_date=dt_util.now().date(),
            )
            if not statistics:
                return

            async_import_statistics(
                self.hass,
                {
                    "statistic_id": entity_id,
                    "source": "recorder",
                    "name": (
                        "Georgia Natural Gas • Estimated daily consumption"
                        + (f" • {self.service_address}" if self.service_address else "")
                    ),
                    "unit_of_measurement": "thm",
                    "unit_class": "energy",
                    "has_sum": True,
                    "mean_type": 0,
                },
                statistics,
            )
        except (HomeAssistantError, ValueError):
            _LOGGER.exception(
                "Unable to import estimated daily GNG consumption statistics."
            )

    def import_gas_service_cost_statistics(self, entity_id: str) -> None:
        """Import daily cost estimates under the Energy cost sensor statistic ID."""

        if not self.records:
            return

        self.gas_service_cost_entity_id = entity_id
        try:
            statistics = build_daily_cost_statistics(
                self.records,
                self.cost_amounts_by_bill_date(),
                timezone=dt_util.get_default_time_zone(),
                as_of_date=dt_util.now().date(),
            )
            if not statistics:
                return

            async_import_statistics(
                self.hass,
                {
                    "statistic_id": entity_id,
                    "source": "recorder",
                    "name": (
                        "Georgia Natural Gas • Estimated daily service cost"
                        + (f" • {self.service_address}" if self.service_address else "")
                    ),
                    "unit_of_measurement": "USD",
                    "unit_class": None,
                    "has_sum": True,
                    "mean_type": 0,
                },
                statistics,
            )
        except (HomeAssistantError, ValueError):
            _LOGGER.exception(
                "Unable to import estimated daily GNG service cost statistics."
            )

    def _update_account_identity(self, records) -> None:
        """Persist the customer-facing account identity and update the entry title."""

        if not records:
            return

        latest = max(records, key=lambda record: record.bill_date)
        self.account_number = latest.account_number
        self.service_address = latest.address
        self.account_display_name = account_display_name(
            self.account_number,
            self.service_address,
        )

        updated_data = {
            **self.config_entry.data,
            CONF_ACCOUNT_NUMBER: self.account_number,
            CONF_SERVICE_ADDRESS: self.service_address,
        }

        if (
            self.config_entry.title != self.account_display_name
            or self.config_entry.data != updated_data
        ):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                title=self.account_display_name,
                data=updated_data,
            )

    async def _async_setup(self) -> None:
        """Load previously stored billing and Price Plan history."""

        try:
            stored = await self.store.async_load()
        except (HomeAssistantError, OSError) as err:
            raise ConfigEntryNotReady(
                "Unable to read stored GNG billing history."
            ) from err

        if stored is None:
            self.records = []
            self.price_plan_records = []
            self.plan_capability = PLAN_CAPABILITY_UNKNOWN
            return

        try:
            if not isinstance(stored, dict):
                raise TypeError("Stored data is not a dictionary.")

            records = stored.get("records")

            if not isinstance(records, list):
                raise TypeError("Stored records are not a list.")

            self.records = [
                deserialize_billing_record(record)
                for record in records
            ]

            price_plan = stored.get("price_plan_records", [])
            if price_plan is None:
                price_plan = []
            if not isinstance(price_plan, list):
                raise TypeError("Stored Price Plan records are not a list.")

            self.price_plan_records = [
                deserialize_price_plan_period(record)
                for record in price_plan
            ]

            capability = stored.get("plan_capability", PLAN_CAPABILITY_UNKNOWN)
            if capability not in (
                PLAN_CAPABILITY_BUDGET_BILLING,
                PLAN_CAPABILITY_NONE,
                PLAN_CAPABILITY_UNKNOWN,
            ):
                capability = PLAN_CAPABILITY_UNKNOWN
            self.plan_capability = capability

        except (KeyError, TypeError, ValueError, ArithmeticError) as err:
            _LOGGER.warning(
                "Stored GNG billing history is invalid; it will be rebuilt "
                "from the customer portal: %s",
                err,
            )
            self.records = []
            self.price_plan_records = []
            self.plan_capability = PLAN_CAPABILITY_UNKNOWN
            return

        self._update_account_identity(self.records)

        _LOGGER.info(
            "Restored %s billing and %s Price Plan GNG records "
            "for the selected account.",
            len(self.records),
            len(self.price_plan_records),
        )

    async def _download_detailed_csv(self, *, full_history: bool) -> str:
        """Download Detailed billing CSV (full window or current bill)."""

        now = dt_util.now().replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        if full_history:
            start = _subtract_months(now, 24)
            return await self.client.download_billing_data(
                account_numbers=[self.account_selection],
                start_date=_iso_utc_date(start),
                end_date=_iso_utc_date(now),
                is_current_bill_selected=False,
            )

        return await self.client.download_billing_data(
            account_numbers=[self.account_selection],
            start_date=_iso_utc_date(now),
            end_date=_iso_utc_date(now),
            is_current_bill_selected=True,
        )

    async def _fetch_price_plan(self):
        """Fetch and parse Price Plan history; tolerate missing plan support."""

        try:
            csv_data = await self.client.download_price_plan_history()
            records = parse_price_plan_csv(csv_data)
            capability = detect_plan_capability(
                records,
                fetch_succeeded=True,
            )
            return records, capability
        except GNGAuthenticationError:
            raise
        except (GNGError, csv.Error, KeyError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Unable to load GNG Price Plan history; "
                "falling back to Detailed cost components: %s",
                err,
            )
            return [], PLAN_CAPABILITY_UNKNOWN

    async def _async_update_data(self):
        """Fetch and persist the selected GNG account's billing history."""

        # Keep interval in sync with options without requiring a full reload path.
        self.update_interval = update_interval_from_options(
            self.config_entry.options
        )

        full_history = not self.records

        try:
            await self.client.login()

            try:
                csv_data = await self._download_detailed_csv(
                    full_history=full_history,
                )
            except GNGError:
                if full_history:
                    raise
                _LOGGER.warning(
                    "Current-bill Detailed download failed; "
                    "retrying with full history window."
                )
                csv_data = await self._download_detailed_csv(
                    full_history=True,
                )

            price_plan_incoming, plan_capability = await self._fetch_price_plan()

        except GNGAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "GNG authentication failed. Reauthentication is required."
            ) from err

        except GNGError as err:
            raise UpdateFailed(
                f"Unable to retrieve GNG billing data: {err}"
            ) from err

        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(
                f"Unable to communicate with GNG: {type(err).__name__}."
            ) from err

        try:
            incoming = parse_billing_csv(csv_data)

            if not incoming:
                if full_history:
                    raise UpdateFailed("GNG returned no billing records.")
                _LOGGER.warning(
                    "Current-bill Detailed download returned no rows; "
                    "retrying with full history window."
                )
                csv_data = await self._download_detailed_csv(full_history=True)
                incoming = parse_billing_csv(csv_data)
                if not incoming:
                    raise UpdateFailed("GNG returned no billing records.")

            issues = validate_billing_records(incoming)

            if issues:
                raise UpdateFailed(
                    "GNG billing data failed validation: "
                    + "; ".join(issues[:5])
                )

        except UpdateFailed:
            raise

        except (csv.Error, KeyError, TypeError, ValueError, ArithmeticError) as err:
            raise UpdateFailed(
                f"Unable to parse GNG billing data: {type(err).__name__}."
            ) from err

        merged = merge_billing_records(
            self.records,
            incoming,
        )
        merged_price_plan = merge_price_plan_periods(
            self.price_plan_records,
            price_plan_incoming,
        )

        try:
            await self.store.async_save(
                {
                    "records": [
                        serialize_billing_record(record)
                        for record in merged
                    ],
                    "price_plan_records": [
                        serialize_price_plan_period(record)
                        for record in merged_price_plan
                    ],
                    "plan_capability": plan_capability,
                }
            )
        except (HomeAssistantError, OSError, TypeError, ValueError) as err:
            raise UpdateFailed(
                f"Unable to save GNG billing history: {type(err).__name__}."
            ) from err

        self.records = merged
        self.price_plan_records = merged_price_plan
        self.plan_capability = plan_capability
        self._update_account_identity(merged)

        if self.gas_consumption_entity_id:
            self.import_gas_consumption_statistics(
                self.gas_consumption_entity_id
            )
        if self.gas_service_cost_entity_id:
            self.import_gas_service_cost_statistics(
                self.gas_service_cost_entity_id
            )

        # Re-importing the complete series is intentional: Home Assistant
        # upserts statistics by timestamp, so this backfills new records and
        # corrects previously imported values without creating duplicates.
        try:
            for metadata, statistics in build_external_statistics(
                merged,
                entry_id=self.entry_id,
                timezone=dt_util.get_default_time_zone(),
            ):
                async_add_external_statistics(
                    self.hass,
                    metadata,
                    statistics,
                )
            for metadata, statistics in build_external_service_cost_statistics(
                merged,
                self.cost_amounts_by_bill_date(),
                entry_id=self.entry_id,
                timezone=dt_util.get_default_time_zone(),
            ):
                async_add_external_statistics(
                    self.hass,
                    metadata,
                    statistics,
                )
        except HomeAssistantError:
            _LOGGER.exception(
                "Unable to import GNG historical statistics into Home Assistant."
            )

        _LOGGER.info(
            "Updated GNG history for the selected account: "
            "%s billing records (%s received), %s Price Plan records, "
            "plan_capability=%s, full_history=%s.",
            len(merged),
            len(incoming),
            len(merged_price_plan),
            plan_capability,
            full_history,
        )

        return merged
