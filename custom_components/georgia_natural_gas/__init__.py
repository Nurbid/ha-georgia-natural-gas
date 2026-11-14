
"""Georgia Natural Gas integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import GeorgiaNaturalGasCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Set up Georgia Natural Gas from a config entry."""

    coordinator = GeorgiaNaturalGasCoordinator(
        hass,
        entry,
        async_get_clientsession(hass),
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Unload Georgia Natural Gas."""

    await hass.config_entries.async_unload_platforms_or_raise(
        entry,
        PLATFORMS,
    )
