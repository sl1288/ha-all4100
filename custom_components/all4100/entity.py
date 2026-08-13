"""Base entity for the ALLNET ALL4100 integration."""

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import All4100Coordinator


class All4100Entity(CoordinatorEntity[All4100Coordinator]):
    """Base class for ALL4100 entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: All4100Coordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        data = coordinator.data

        self._attr_device_info = DeviceInfo(
            # The ALL4100 exposes neither a MAC address nor a serial number, so
            # the config entry ID is the only stable identifier available.
            identifiers={(DOMAIN, entry.entry_id)},
            name=data.device_name,
            manufacturer=MANUFACTURER,
            model=data.model,
            sw_version=data.firmware,
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )
