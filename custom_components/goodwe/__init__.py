"""The Goodwe inverter component."""
from datetime import timedelta
import logging

from goodwe import InverterError, RequestFailedException, connect

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MODEL_FAMILY,
    CONF_NETWORK_RETRIES,
    CONF_NETWORK_TIMEOUT,
    DEFAULT_NETWORK_RETRIES,
    DEFAULT_NETWORK_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE_INFO,
    KEY_INVERTER,
    PLATFORMS,
)
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Goodwe components from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    name = entry.title
    host = entry.data[CONF_HOST]
    model_family = entry.data[CONF_MODEL_FAMILY]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    network_retries = entry.options.get(CONF_NETWORK_RETRIES, DEFAULT_NETWORK_RETRIES)
    network_timeout = entry.options.get(CONF_NETWORK_TIMEOUT, DEFAULT_NETWORK_TIMEOUT)

    # Connect to Goodwe inverter
    try:
        inverter = await connect(
            host=host,
            family=model_family,
            comm_addr=0,
            timeout=network_timeout,
            retries=network_retries,
        )
    except InverterError as err:
        raise ConfigEntryNotReady from err

    device_info = DeviceInfo(
        configuration_url="https://www.semsportal.com",
        identifiers={(DOMAIN, inverter.serial_number)},
        name=entry.title,
        manufacturer="GoodWe",
        model=inverter.model_name,
        sw_version=f"{inverter.software_version} ({inverter.arm_version})",
    )

    async def async_update_data():
        """Fetch data from the inverter."""
        try:
            return await inverter.read_runtime_data()
        except RequestFailedException as ex:
            # UDP communication with inverter is by definition unreliable.
            # It is rather normal in many environments to fail to receive
            # proper response in usual time, so we intentionally ignore isolated
            # failures and report problem with availability only after
            # consecutive streak of 3 of failed requests.
            if ex.consecutive_failures_count < 3:
                _LOGGER.debug(
                    "No response received (streak of %d)", ex.consecutive_failures_count
                )
                # return empty dictionary, sensors will keep their previous values
                return {}
            # Inverter does not respond anymore (e.g. it went to sleep mode)
            _LOGGER.debug(
                "Inverter not responding (streak of %d)", ex.consecutive_failures_count
            )
            raise UpdateFailed(ex) from ex
        except InverterError as ex:
            raise UpdateFailed(ex) from ex

    # Create update coordinator
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=scan_interval),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_INVERTER: inverter,
        KEY_COORDINATOR: coordinator,
        KEY_DEVICE_INFO: device_info,
    }

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if len(hass.data[DOMAIN]) == 1:
        await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    if not hass.data[DOMAIN]:
        await async_unload_services(hass)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
