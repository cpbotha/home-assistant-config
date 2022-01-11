"""GoodWe PV inverter selection settings entities."""
import logging

from goodwe import Inverter, InverterError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, KEY_DEVICE_INFO, KEY_INVERTER

_LOGGER = logging.getLogger(__name__)


INVERTER_OPERATION_MODES = [
    "General mode",
    "Off grid mode",
    "Backup mode",
    "Eco mode",
    "Eco charge mode",
    "Eco discharge mode",
]

OPERATION_MODE = SelectEntityDescription(
    key="operation_mode",
    name="Inverter operation mode",
    icon="mdi:solar-power",
    entity_category=ENTITY_CATEGORY_CONFIG,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the inverter select entities from a config entry."""
    inverter = hass.data[DOMAIN][config_entry.entry_id][KEY_INVERTER]
    device_info = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE_INFO]

    # read current operating mode from the inverter
    try:
        active_mode = await inverter.get_operation_mode()
    except (InverterError, ValueError):
        # Inverter model does not support this setting
        _LOGGER.debug("Could not read inverter operation mode")
    else:
        if 0 <= active_mode < len(INVERTER_OPERATION_MODES):
            async_add_entities(
                [
                    InverterOperationModeEntity(
                        device_info,
                        OPERATION_MODE,
                        inverter,
                        INVERTER_OPERATION_MODES[active_mode],
                    )
                ]
            )


class InverterOperationModeEntity(SelectEntity):
    """Entity representing the inverter operation mode."""

    _attr_should_poll = False

    def __init__(
        self,
        device_info: DeviceInfo,
        description: SelectEntityDescription,
        inverter: Inverter,
        current_mode: str,
    ) -> None:
        """Initialize the inverter operation mode setting entity."""
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_options = INVERTER_OPERATION_MODES
        self._attr_current_option = current_mode
        self._inverter: Inverter = inverter

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        operation_mode = INVERTER_OPERATION_MODES.index(option)
        eco_mode_power = 100
        if operation_mode in (4, 5):
            eco_mode_power = self.hass.states.get("number.eco_mode_power").state
        await self._inverter.set_operation_mode(operation_mode, eco_mode_power)
        self._attr_current_option = option
        self.async_write_ha_state()
