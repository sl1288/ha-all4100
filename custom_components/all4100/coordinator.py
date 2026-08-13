"""Coordinator for the ALLNET ALL4100 integration."""

import logging
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import All4100AuthError, All4100Client, All4100Data, All4100Error
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type All4100ConfigEntry = ConfigEntry[All4100Coordinator]


class All4100Coordinator(DataUpdateCoordinator[All4100Data]):
    """Class to manage fetching ALL4100 data."""

    config_entry: All4100ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: All4100ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = All4100Client(
            host=entry.data[CONF_HOST],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=async_get_clientsession(hass),
        )

    @override
    async def _async_update_data(self) -> All4100Data:
        """Fetch the current relay states from the device."""
        try:
            return await self.client.async_get_data()
        except All4100AuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except All4100Error as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
            ) from err
