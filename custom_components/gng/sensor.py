"""Sensor platform for GNG."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PLAN_CAPABILITY_BUDGET_BILLING, SHORT_NAME, LONG_NAME
from .coordinator import GeorgiaNaturalGasCoordinator
from .models import BillingRecord
from .price_plan import PricePlanPeriod
from .statistics import (
    build_daily_consumption_statistics,
    build_daily_cost_statistics,
)


@dataclass(frozen=True, kw_only=True)
class GNGSensorDescription(SensorEntityDescription):
    """Describe a GNG billing sensor."""

    value_fn: Callable[
        [BillingRecord],
        str | int | float | Decimal | date | None,
    ] | None = None
    price_plan_value_fn: Callable[
        [PricePlanPeriod],
        str | int | float | Decimal | date | None,
    ] | None = None
    requires_price_plan: bool = False


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
        key="gas_consumption",
        name="Gas Consumption",
        icon="mdi:fire",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.THERM,
        suggested_display_precision=3,
        value_fn=lambda record: record.gas_used_therms,
    ),
    GNGSensorDescription(
        key="gas_service_cost",
        name="Gas Service Cost",
        icon="mdi:cash-multiple",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
    ),
    GNGSensorDescription(
        key="actual_bill_charges",
        name="Actual Bill Charges",
        icon="mdi:receipt",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        price_plan_value_fn=lambda record: record.actual_bill_charges,
        requires_price_plan=True,
    ),
    GNGSensorDescription(
        key="budget_billing_installment",
        name="Budget Billing Installment",
        icon="mdi:calendar-month",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        price_plan_value_fn=lambda record: record.installment_amount,
        requires_price_plan=True,
    ),
    GNGSensorDescription(
        key="monthly_budget_variance",
        name="Monthly Budget Variance",
        icon="mdi:chart-line-variant",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        price_plan_value_fn=lambda record: record.monthly_variance,
        requires_price_plan=True,
    ),
    GNGSensorDescription(
        key="accumulated_budget_variance",
        name="Accumulated Budget Variance",
        icon="mdi:chart-timeline-variant",
        native_unit_of_measurement="USD",
        suggested_display_precision=2,
        price_plan_value_fn=lambda record: record.accumulated_variance,
        requires_price_plan=True,
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

        device_name = SHORT_NAME
        if coordinator.service_address:
            device_name = f"{device_name} • {coordinator.service_address}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=device_name,
            manufacturer=LONG_NAME,
        )

    async def async_added_to_hass(self) -> None:
        """Backfill daily estimates after Home Assistant assigns the entity ID."""

        await super().async_added_to_hass()
        if self.entity_description.key == "gas_consumption":
            self.coordinator.import_gas_consumption_statistics(self.entity_id)
        elif self.entity_description.key == "gas_service_cost":
            self.coordinator.import_gas_service_cost_statistics(self.entity_id)

    @property
    def available(self) -> bool:
        """Price Plan sensors stay unavailable when the plan is absent."""

        if not super().available:
            return False
        if not self.entity_description.requires_price_plan:
            return True
        return (
            self.coordinator.plan_capability == PLAN_CAPABILITY_BUDGET_BILLING
            and bool(self.coordinator.price_plan_records)
        )

    @property
    def native_value(self) -> str | int | float | Decimal | date | None:
        """Return the latest billing-period or cumulative Energy value."""

        if self.entity_description.key == "gas_consumption":
            if not self.coordinator.data:
                return None
            statistics = build_daily_consumption_statistics(
                self.coordinator.data,
                timezone=dt_util.get_default_time_zone(),
                as_of_date=dt_util.now().date(),
            )
            return statistics[-1]["state"] if statistics else 0

        if self.entity_description.key == "gas_service_cost":
            if not self.coordinator.data:
                return None
            statistics = build_daily_cost_statistics(
                self.coordinator.data,
                self.coordinator.cost_amounts_by_bill_date(),
                timezone=dt_util.get_default_time_zone(),
                as_of_date=dt_util.now().date(),
            )
            return statistics[-1]["state"] if statistics else 0

        if self.entity_description.requires_price_plan:
            if not self.coordinator.price_plan_records:
                return None
            latest_plan = max(
                self.coordinator.price_plan_records,
                key=lambda record: record.bill_date,
            )
            if self.entity_description.price_plan_value_fn is None:
                return None
            return self.entity_description.price_plan_value_fn(latest_plan)

        if not self.coordinator.data:
            return None

        latest = max(
            self.coordinator.data,
            key=lambda record: record.bill_date,
        )
        if self.entity_description.value_fn is None:
            return None
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

        attributes = {
            "bill_date": latest.bill_date.isoformat(),
            "billing_period_start": latest.bill_from_date.isoformat(),
            "billing_period_end": latest.bill_to_date.isoformat(),
            "days_of_service": latest.days_of_service,
            "plan_capability": self.coordinator.plan_capability,
        }
        if self.entity_description.key == "gas_consumption":
            today = dt_util.now().date()
            yesterday = date.fromordinal(today.toordinal() - 1)
            attributes.update(
                {
                    "estimated_daily_allocation": True,
                    "estimated_through": yesterday.isoformat(),
                    "consumption_source": "GNG billed therms",
                }
            )
        elif self.entity_description.key == "gas_service_cost":
            today = dt_util.now().date()
            yesterday = date.fromordinal(today.toordinal() - 1)
            cost_source = self.coordinator.cost_sources_by_bill_date().get(
                latest.bill_date,
                "unknown",
            )
            attributes.update(
                {
                    "estimated_daily_allocation": True,
                    "estimated_through": yesterday.isoformat(),
                    "cost_source": cost_source,
                    "latest_period_cost": str(
                        self.coordinator.cost_amounts_by_bill_date().get(
                            latest.bill_date,
                            Decimal(0),
                        )
                    ),
                }
            )
        return attributes
