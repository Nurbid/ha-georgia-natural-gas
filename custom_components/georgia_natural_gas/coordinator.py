"""Data coordinator for Georgia Natural Gas."""

import calendar
import csv
import logging
from datetime import UTC

import aiohttp
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
    CONF_ACCOUNT_ID,
    DEFAULT_ACCOUNT_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    STORAGE_VERSION,
)
from .models import (
    deserialize_billing_record,
    merge_billing_records,
    parse_billing_csv,
    serialize_billing_record,
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
            always_update=False,
        )

        self.client = GeorgiaNaturalGasClient(
            session,
            entry.data["username"],
            entry.data["password"],
        )
        self.account_id = entry.options.get(
            CONF_ACCOUNT_ID,
            DEFAULT_ACCOUNT_ID,
        )

        self.store = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}_{entry.entry_id}",
        )

        self.records_by_account = {}
        self.records = []

    async def _async_setup(self) -> None:
        """Load previously stored billing history."""

        try:
            stored = await self.store.async_load()
        except (HomeAssistantError, OSError) as err:
            raise ConfigEntryNotReady(
                "Unable to read stored GNG billing history."
            ) from err

        if stored is None:
            self.records_by_account = {}
            self.records = []
            return

        try:
            if not isinstance(stored, dict):
                raise TypeError("Stored data is not a dictionary.")

            if "records_by_account" in stored:
                stored_by_account = stored["records_by_account"]

                if not isinstance(stored_by_account, dict):
                    raise TypeError("Stored account history is not a dictionary.")

                self.records_by_account = {
                    account_id: [
                        deserialize_billing_record(record)
                        for record in records
                    ]
                    for account_id, records in stored_by_account.items()
                    if isinstance(account_id, str) and isinstance(records, list)
                }

                if len(self.records_by_account) != len(stored_by_account):
                    raise TypeError("Stored account history is invalid.")

            else:
                # Migrate the original single-account storage format.
                records = stored.get("records")

                if not isinstance(records, list):
                    raise TypeError("Stored records are not a list.")

                self.records_by_account = {
                    DEFAULT_ACCOUNT_ID: [
                        deserialize_billing_record(record)
                        for record in records
                    ]
                }

            self.records = self.records_by_account.get(self.account_id, [])

        except (KeyError, TypeError, ValueError, ArithmeticError) as err:
            _LOGGER.warning(
                "Stored GNG billing history is invalid; it will be rebuilt "
                "from the customer portal: %s",
                err,
            )
            self.records_by_account = {}
            self.records = []
            return

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
                account_numbers=[self.account_id],
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
            self.records_by_account.get(self.account_id, []),
            incoming,
        )
        updated_records_by_account = {
            **self.records_by_account,
            self.account_id: merged,
        }

        try:
            await self.store.async_save(
                {
                    "records_by_account": {
                        account_id: [
                            serialize_billing_record(record)
                            for record in records
                        ]
                        for account_id, records in updated_records_by_account.items()
                    }
                }
            )
        except (HomeAssistantError, OSError, TypeError, ValueError) as err:
            raise UpdateFailed(
                f"Unable to save GNG billing history: {type(err).__name__}."
            ) from err

        self.records_by_account = updated_records_by_account
        self.records = merged

        _LOGGER.info(
            "Updated GNG billing history for the selected account: "
            "%s records (%s received).",
            len(merged),
            len(incoming),
        )

        return merged
