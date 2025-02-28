"""Integration for Midea Smart AC."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from msmart.device import air_conditioning as ac
try:
    # Try to import newer __version__ attribute
    from msmart import __version__ as MSMART_VERISON
except ImportError:
    # Fallback to older VERSION attribute
    from msmart.device import VERSION as MSMART_VERISON


# Local constants
from .const import (
    DOMAIN,
    CONF_K1
)
from . import helpers

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a Midea AC device from a config entry."""

    _LOGGER.info(
        f"Starting midea-ac-py. Using msmart version {MSMART_VERISON}.")

    # Ensure the global data dict exists
    hass.data.setdefault(DOMAIN, {})

    # Get config data from entry
    config = config_entry.data

    # Attempt to get device from global data
    id = config.get(CONF_ID)
    device = hass.data[DOMAIN].get(id)

    # Construct a new device if necessary
    if device is None:
        # Construct the device
        id = config.get(CONF_ID)
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        device = ac(host, int(id), port)

        # Configure token and k1 as needed
        token = config.get(CONF_TOKEN)
        k1 = config.get(CONF_K1)
        if token and k1:
            await hass.async_add_executor_job(device.authenticate, k1, token)

        hass.data[DOMAIN][id] = device

    # Query device capabilities
    if helpers.method_exists(device, "get_capabilities"):
        _LOGGER.info("Querying device capabilities.")
        await hass.async_add_executor_job(device.get_capabilities)

    # Create platform entries
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "climate"))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor"))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor"))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "switch"))

    # Reload entry when its updated
    config_entry.async_on_unload(
        config_entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:

    # Get config data from entry
    config = config_entry.data

    # Remove device from global data
    id = config.get(CONF_ID)
    hass.data[DOMAIN].pop(id)

    await hass.config_entries.async_forward_entry_unload(config_entry, "climate")
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(config_entry, "switch")
    await hass.config_entries.async_forward_entry_unload(config_entry, "binary_sensor")

    return True


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(config_entry.entry_id)
