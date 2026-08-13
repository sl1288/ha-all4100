"""Switch platform for the ALLNET ALL4100."""

from typing import Any, override

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import All4100Error
from .const import DOMAIN
from .coordinator import All4100ConfigEntry, All4100Coordinator
from .entity import All4100Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: All4100ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ALL4100 relay switches."""
    coordinator = entry.runtime_data

    async_add_entities(
        All4100RelaySwitch(coordinator, index) for index in coordinator.data.relays
    )


class All4100RelaySwitch(All4100Entity, SwitchEntity):
    """Representation of a single ALL4100 relay."""

    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(self, coordinator: All4100Coordinator, index: int) -> None:
        """Initialize the relay switch."""
        super().__init__(coordinator)
        self._index = index
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_relay_{index}"
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Copy relay name and state out of the coordinator data."""
        relay = self.coordinator.data.relays[self._index]
        # The name is device provided (rnN) and editable in the ALL4100 web
        # interface, so it is refreshed on every poll rather than fixed at setup.
        self._attr_name = relay.name
        self._attr_is_on = relay.is_on

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()

    async def _async_set_relay(self, is_on: bool) -> None:
        """Switch the relay and reflect the new state immediately."""
        try:
            await self.coordinator.client.async_set_relay(self._index, is_on)
        except All4100Error as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_turn_on_failed"
                if is_on
                else "switch_turn_off_failed",
                translation_placeholders={
                    "name": self.coordinator.data.relays[self._index].name
                },
            ) from err

        self._attr_is_on = is_on
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the relay on."""
        await self._async_set_relay(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the relay off."""
        await self._async_set_relay(False)
