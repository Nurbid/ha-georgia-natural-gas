"""Sensor platform for Georgia Natural Gas."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GeorgiaNaturalGasCoordinator
from .models import BillingRecord


@dataclass(frozen=True, kw_only=True)
class GNGSensorDescription(SensorEntityDescription):
    """Describe a GNG billing sensor."""

    value_fn: Callable[
        [BillingRecord],
        str | int | float | Decimal | date | None,
    ]


SENSORS: tuple[GNGSensorDescription, ...] = (
    GNGSensorDescription(
        key="gas_used_therms",
        name="Gas Used",
        icon="mdi:fire",
        native_unit_of_measurement="therm",
        suggested_display_precision=3,
        value_fn=lambda record: record.gas_used_therms,
    ),
    GNGSensorDescription(
        key="gas_charges_excl_taxes",
        name="Gas Charges",
        icon="mdi:cash",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        value_fn=lambda record: record.gas_charges_excl_taxes,
    ),
    GNGSensorDescription(
        key="other_charges",
        name="Other Charges",
        icon="mdi:receipt-text",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        value_fn=lambda record: record.other_charges,
    ),
    GNGSensorDescription(
        key="promotional_discounts",
        name="Promotional Discounts",
        icon="mdi:tag-minus",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        value_fn=lambda record: record.promotional_discounts,
    ),
    GNGSensorDescription(
        key="taxes",
        name="Taxes",
        icon="mdi:cash-check",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        value_fn=lambda record: record.taxes,
    ),
    GNGSensorDescription(
        key="sum_of_payments",
        name="Payments",
        icon="mdi:bank-transfer",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        value_fn=lambda record: record.sum_of_payments,
    ),
    GNGSensorDescription(
        key="balance_forward",
        name="Balance Forward",
        icon="mdi:scale-balance",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        value_fn=lambda record: record.balance_forward,
    ),
    GNGSensorDescription(
        key="budget_billing_amount",
        name="Budget Billing Amount",
        icon="mdi:calendar-month",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        value_fn=lambda record: record.budget_billing_amount,
    ),
    GNGSensorDescription(
        key="guaranteed_billing_amount",
        name="Guaranteed Billing Amount",
        icon="mdi:shield-check",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        value_fn=lambda record: record.guaranteed_billing_amount,
    ),
    GNGSensorDescription(
        key="amount_due",
        name="Amount Due",
        icon="mdi:cash-clock",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        value_fn=lambda record: record.amount_due,
    ),
    GNGSensorDescription(
        key="meter_reading",
        name="Meter Reading",
        icon="mdi:counter",
        native_unit_of_measurement="CCF",
        value_fn=lambda record: record.meter_reading,
    ),
    GNGSensorDescription(
        key="heating_degree_days",
        name="Heating Degree Days",
        icon="mdi:weather-snowy",
        native_unit_of_measurement="°F-days",
        suggested_display_precision=1,
        value_fn=lambda record: record.heating_degree_days,
    ),
    GNGSensorDescription(
        key="average_temperature",
        name="Average Temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        suggested_display_precision=1,
        value_fn=lambda record: record.average_temperature,
    ),
    GNGSensorDescription(
        key="days_of_service",
        name="Days of Service",
        icon="mdi:calendar-range",
        native_unit_of_measurement="d",
        value_fn=lambda record: record.days_of_service,
    ),
    GNGSensorDescription(
        key="bill_date",
        name="Bill Date",
        icon="mdi:calendar",
        value_fn=lambda record: record.bill_date,
    ),
    GNGSensorDescription(
        key="billing_period_start",
        name="Billing Period Start",
        icon="mdi:calendar-start",
        value_fn=lambda record: record.bill_from_date,
    ),
    GNGSensorDescription(
        key="billing_period_end",
        name="Billing Period End",
        icon="mdi:calendar-end",
        value_fn=lambda record: record.bill_to_date,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GNG billing sensors."""

    coordinator = entry.runtime_data

    async_add_entities(
        GNGSensor(coordinator, entry.entry_id, description)
        for description in SENSORS
    )


class GNGSensor(
    CoordinatorEntity[GeorgiaNaturalGasCoordinator],
    SensorEntity,
):
    """Represent a GNG billing sensor."""

    entity_description: GNGSensorDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GeorgiaNaturalGasCoordinator,
        entry_id: str,
        description: GNGSensorDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

        device_name = "Georgia Natural Gas"
        if coordinator.service_address:
            device_name = f"{device_name} • {coordinator.service_address}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=device_name,
            manufacturer="Georgia Natural Gas",
        )

    @property
    def native_value(self) -> str | int | float | Decimal | date | None:
        """Return the latest billing-period value."""

        if not self.coordinator.data:
            return None

        latest = max(
            self.coordinator.data,
            key=lambda record: record.bill_date,
        )

        return self.entity_description.value_fn(latest)

    @property
    def extra_state_attributes(self) -> dict[str, str | int] | None:
        """Return the billing period associated with this sensor value."""

        if not self.coordinator.data:
            return None

        latest = max(
            self.coordinator.data,
            key=lambda record: record.bill_date,
        )

        return {
            "bill_date": latest.bill_date.isoformat(),
            "billing_period_start": latest.bill_from_date.isoformat(),
            "billing_period_end": latest.bill_to_date.isoformat(),
            "days_of_service": latest.days_of_service,
        }
