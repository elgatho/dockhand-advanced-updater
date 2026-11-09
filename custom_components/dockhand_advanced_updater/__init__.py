"""Dockhand Advanced Updater integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DockhandClient
from .const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from .coordinator import DockhandCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]

type DockhandConfigEntry = ConfigEntry[DockhandCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DockhandConfigEntry) -> bool:
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client = DockhandClient(session, entry.data[CONF_URL], entry.data.get(CONF_TOKEN))
    coordinator = DockhandCoordinator(hass, entry, client)
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    coordinator.async_start()
    entry.async_on_unload(coordinator.async_stop)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: DockhandConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DockhandConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: DockhandConfigEntry) -> None:
    await DockhandCoordinator(
        hass, entry, DockhandClient(async_get_clientsession(hass), entry.data[CONF_URL], None)
    ).async_remove_storage()
