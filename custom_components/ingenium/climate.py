"""Support for Ingenium climate gateways."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    FAN_OFF,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import ATTR_MANUFACTURER, DOMAIN, CONF_MAC
from .device import BusDeviceType

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: dict,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Climate Device sensors."""

    # Add devices
    async_add_entities(
        [
            IngeniumClimate(config_entry, dev.address, dev.output, dev.label)
            for dev in config_entry.runtime_configuration["devices"]
            if dev.device_type in [BusDeviceType.AC_GATEWAY_LG]
        ]
    )


class IngeniumClimate(CoordinatorEntity, ClimateEntity):
    def __init__(
        self,
        config_entry: dict,
        address: int,
        unit_id: int = 0,
        label: str | None = None,
    ):
        super().__init__(config_entry.runtime_configuration["coordinator"])
        features: ClimateEntityFeature = ClimateEntityFeature(0)
        features |= ClimateEntityFeature.TARGET_TEMPERATURE
        features |= ClimateEntityFeature.FAN_MODE

        self._parent_config_entry = config_entry
        self._address = address
        self._unit_id = unit_id
        self._attr_has_entity_name = True
        self._attr_name = label
        self._attr_unique_id = (
            f"{config_entry.data.get(CONF_MAC)}_busing_{address}_unit_{unit_id}"
        )
        self._attr_temperature_unit = "°C"
        self._attr_hvac_modes = ["off", "heat", "cool", "auto"]
        self._attr_hvac_mode = "off"
        self._attr_precision = 0.5
        self._attr_supported_features = features
        self.hvac_modes = [
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
            HVACMode.OFF,
        ]
        self.fan_mode = None
        self.fan_modes = [FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    def _handle_coordinator_update(self) -> None:
        if self._address not in self.coordinator.data:
            return

        service_call = self.coordinator.data[self._address]

        # Note: This type of device handles up to 63 units with 4 registers each:
        #   data1 == register + self._unit_id * 4
        # Unit Id 0 = data1: 0-4
        # Unit Id 1 = data1: 1-5
        # ..
        # Unit Id 63 = data1: 252 - 255
        res = [
            self._read_bus_message(msg)
            for msg in service_call["bus_messages"]
            if msg["command"] == 4
            if msg["data1"] >= (self._unit_id * 4)
            and msg["data1"] < (self._unit_id * 4 + 4)
            if "bus_messages" in service_call
        ]
        # Request update of HA state if any message resulted in an update to the entity state
        if any(res):
            _LOGGER.info("Updating UI state")
            self.async_write_ha_state()

    def _read_bus_message(self, msg) -> bool:
        if msg["data1"] % 4 == 0:  # estado
            if msg["data2"] & 3 == 3:  # AC is ON
                self._attr_state = STATE_ON
            elif msg["data2"] & 3 == 2:  # AC is OFF
                self._attr_state = STATE_OFF
            elif msg["data2"] & 3 == 0:  # AC controls unavailable
                self._attr_state = STATE_UNAVAILABLE
            else:
                return

        elif msg["data1"] % 4 == 1:  # modoFuncionamiento
            if msg["data2"] < 16:
                self._attr_fan_mode = FAN_OFF
                self._attr_hvac_mode = HVACMode.OFF
            else:
                # Fan setting (mask upper 3 bits)
                if msg["data2"] & 0xF0 == 16:
                    self._attr_fan_mode = FAN_LOW
                elif msg["data2"] & 0xF0 == 32:
                    self._attr_fan_mode = FAN_MEDIUM
                elif msg["data2"] & 0xF0 == 48:
                    self._attr_fan_mode = FAN_HIGH
                elif msg["data2"] & 0xF0 == 64:
                    self._attr_fan_mode = FAN_AUTO
                # HVAC mode (mask lower 3 bits)
                if msg["data2"] & 0x0F == 0:
                    self._attr_hvac_mode = HVACMode.COOL
                elif msg["data2"] & 0x0F == 1:
                    self._attr_hvac_mode = HVACMode.DRY
                elif msg["data2"] & 0x0F == 2:
                    self._attr_hvac_mode = HVACMode.FAN_ONLY
                elif msg["data2"] & 0x0F == 3:
                    self._attr_hvac_mode = HVACMode.AUTO
                elif msg["data2"] & 0x0F == 4:
                    self._attr_hvac_mode = HVACMode.HEAT
        elif msg["data1"] % 4 == 2:  # consigna
            self.target_temperature = msg["data2"] + 15
        elif msg["data1"] % 4 == 3:  # ambiente
            if (164 - msg["data2"]) / 2 > 50:
                self.current_temperature = 0
            else:
                self.current_temperature = (164 - msg["data2"]) / 2

        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._address)
            },
            name=f"LG-I {self._address}",
            manufacturer=ATTR_MANUFACTURER,
            model="BUSing-LGAC-I",
            via_device=(DOMAIN, self._parent_config_entry.entry_id),
        )
