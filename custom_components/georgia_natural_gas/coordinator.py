"""Data coordinator for Georgia Natural Gas."""

import calendar
import csv
import logging
from datetime import UTC

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
    DEFAULT_ACCOUNT_SELECTION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    STORAGE_VERSION,
)
from .identity import account_display_name
from .models import (
    deserialize_billing_record,
    merge_billing_records,
    parse_billing_csv,
    serialize_billing_record,
)
from .statistics import (
    build_daily_consumption_statistics,
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


class GeorgiaNaturalGasCoordinator(DataUpdateCoordinator):
    """Manage GNG billing data and historical storage."""

    def __init__(self, hass, entry, session):
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
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
        self.gas_consumption_entity_id = None

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
        """Load previously stored billing history for the selected account."""

        try:
            stored = await self.store.async_load()
        except (HomeAssistantError, OSError) as err:
            raise ConfigEntryNotReady(
                "Unable to read stored GNG billing history."
            ) from err

        if stored is None:
            self.records = []
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

        except (KeyError, TypeError, ValueError, ArithmeticError) as err:
            _LOGGER.warning(
                "Stored GNG billing history is invalid; it will be rebuilt "
                "from the customer portal: %s",
                err,
            )
            self.records = []
            return

        self._update_account_identity(self.records)

        _LOGGER.info(
            "Restored %s historical GNG billing records for the selected account.",
            len(self.records),
        )

    async def _async_update_data(self):
        """Fetch and persist the selected GNG account's billing history."""

        try:
            await self.client.login()

            now = dt_util.now().replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            start = _subtract_months(now, 24)

            start_date = (
                start.astimezone(UTC)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            )
            end_date = (
                now.astimezone(UTC)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            )

            csv_data = await self.client.download_billing_data(
                account_numbers=[self.account_selection],
                start_date=start_date,
                end_date=end_date,
            )

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

        try:
            await self.store.async_save(
                {
                    "records": [
                        serialize_billing_record(record)
                        for record in merged
                    ]
                }
            )
        except (HomeAssistantError, OSError, TypeError, ValueError) as err:
            raise UpdateFailed(
                f"Unable to save GNG billing history: {type(err).__name__}."
            ) from err

        self.records = merged
        self._update_account_identity(merged)

        # Refresh the Energy sensor's historical series after new billing data
        # arrives. The entity ID is supplied by the sensor once it is registered.
        if self.gas_consumption_entity_id:
            self.import_gas_consumption_statistics(
                self.gas_consumption_entity_id
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
        except HomeAssistantError:
            _LOGGER.exception(
                "Unable to import GNG historical statistics into Home Assistant."
            )

        _LOGGER.info(
            "Updated GNG billing history for the selected account: "
            "%s records (%s received).",
            len(merged),
            len(incoming),
        )

        return merged
