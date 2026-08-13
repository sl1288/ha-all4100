"""The ALLNET ALL4100 integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import All4100ConfigEntry, All4100Coordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: All4100ConfigEntry) -> bool:
    """Set up ALLNET ALL4100 from a config entry."""
    coordinator = All4100Coordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: All4100ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
