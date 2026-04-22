"""
Support for Ingenium BUSing Actuators

Received message: {'raw': 'fefe04000100010120', 'command': 4, 'origin': 1, 'destination': 1, 'data1': 1, 'data2': 32}
  data1:0 == Read/Write the state of inputs
    Device  Type  Bit 7 Bit 6 Bit 5 Bit 4 Bit 3 Bit 2 Bit 1 Bit 0
            6E6S  E6    E5    E4    E3    E2    E1    —     —
            4E4S  E4    E3    E2    E1    —     —     —     —
            2E2S  E2    E1    —     —     —     —     —     —
  data1:1 == Read/Write state of outputs
    Device  Type  Bit 7 Bit 6 Bit 5 Bit 4 Bit 3 Bit 2 Bit 1 Bit 0
            6E6S  —     —     Z6    Z5    Z4    Z3    Z2    Z1
            4E4S  —     —     Z4    Z3    Z2    Z1    —     —
            2E2S  —     —     Z2    Z1    —     —     —     —

Received message: {'raw': 'fefe0400010001ff01', 'command': 4, 'origin': 1, 'destination': 1, 'data1': 255, 'data2': 1}
  NOTE: ALL DEVICES RESPONDS TO ADDRESS 255, IN ADDITION TO THE ONE THEY HAVE
  ADDRESSED. A SINGLE DEVICE, MAKE A DIAGNOSTIC TO ADDRESS 255, TO GET TO KNOW
  YOUR ADDRESS.
"""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MAC
from .device import BusDeviceType, Device
from .entity import BaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: dict,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Climate Device sensors."""

    actuators = {}

    # Structure Actuator devices by address and outputs
    for dev in config_entry.runtime_configuration["devices"]:
        if dev.device_type in [BusDeviceType.ACTUATOR_ALL_NOTHING]:
            if dev.address in actuators.keys():
                actuators[dev.address][dev.output] = dev
            else:
                actuators[dev.address] = {dev.output: dev}

    _LOGGER.info(f"Actuator switches found: {actuators}")

    for address in actuators.keys():
        # Concatenated string of outputs
        # outputs = '-'.join()
        outputs = list(actuators[address].keys())
        outputs.sort()
        if outputs == [4, 5]:
            model = "2E2S/2E2S-30A"
        elif outputs == [2, 3, 4, 5]:
            model = "4E4S/4E4S-30A/4E4S-F4A"
        elif outputs == [0, 1, 2, 3, 4, 5]:
            model = "6E6S/6E6S-F2A"
        elif outputs == [0, 1, 2, 3, 4, 5, 6, 7]:
            model = "4E8S"
        else:
            _LOGGER.warning(
                f"Unknown BUSing actuator device, address={address}, outputs={outputs}"
            )
            break

        _LOGGER.info(f"Adding Type {model} BUSing actuator at address={address}")

        async_add_entities(
            [
                IngeniumBinarySwitch(config_entry, dev, model)
                for dev in actuators[address].values()
            ]
        )


class IngeniumBinarySwitch(BaseEntity, SwitchEntity):
    def __init__(
        self,
        config_entry: dict,
        dev: Device,
        model: str = "",
    ):
        super().__init__(config_entry, dev, model)

        self._attr_unique_id = (
            f"{config_entry.data.get(CONF_MAC)}_busing_{dev.address}_{dev.output}"
        )
        self._attr_name = dev.label
        self._output = dev.output

    def _read_bus_message(self, msg) -> bool:
        if msg["data1"] == 1:  # All outputs state
            self._attr_is_on = bool(msg["data2"] & 2**self._output)
            return True
        elif msg["data1"] == 2:  # Change state command for one output
            if msg["data2"] == self._output:
                _LOGGER.debug(f"Switching ON {msg['data2']} ==  {self._output}")
                self._attr_is_on = True
            elif msg["data2"] == (self._output + 8):
                _LOGGER.debug(f"Switching OFF {msg['data2']} ==  {self._output} + 8")
                self._attr_is_on = False
            else:
                _LOGGER.debug(
                    f"Ignoring: {msg['data2']} !=  {self._output} (My ON state) != {self._output + 8} (My OFF state)"
                )
                return False

            return True

        return False
