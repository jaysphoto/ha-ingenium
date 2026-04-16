"""Support for Ingenium climate gateways."""

import logging

from homeassistant.core import HomeAssistant
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
        self, config_entry: dict, address: int, unit: int = 0, label: str | None = None
    ):
        super().__init__(config_entry.runtime_configuration["coordinator"])
        features: ClimateEntityFeature = ClimateEntityFeature(0)
        features |= ClimateEntityFeature.TARGET_TEMPERATURE
        features |= ClimateEntityFeature.FAN_MODE

        self._parent_config_entry = config_entry
        self._address = address
        self._unit = unit
        self._is_on = None
        self._attr_has_entity_name = True
        self._attr_name = label
        self._attr_unique_id = f"{config_entry.data.get(CONF_MAC)}_busing_{address}"
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
        if self.address not in self.coordinator.data:
            return

        service_call = self.coordinator.data[self.address]

        res = [
            self._read_bus_message(msg)
            for msg in service_call["bus_messages"]
            if msg["command"] == 4
            # TODO: filter on _self._unit
            if "bus_messages" in service_call
        ]

        if not self._is_on:
            self._attr_hvac_mode = HVACMode.OFF

        # Request update of HA state if any message resulted in an update to the entity state

        any(res) and (_LOGGER.info("Updating UI state") or self.async_write_ha_state())

    def _read_bus_message(self, msg) -> bool:
        if msg["data1"] == 0:  # estado
            if msg["data2"] & 3 == 3:
                self._is_on = True
            else:
                self._is_on = False

        elif msg["data1"] == 1:  # modoFuncionamiento
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

            # Fan setting (mask upper 3 bits)
            if msg["data2"] & 0xF0 == 0:
                self._attr_fan_mode = FAN_OFF
            elif msg["data2"] & 0xF0 == 16:
                self._attr_fan_mode = FAN_LOW
            elif msg["data2"] & 0xF0 == 32:
                self._attr_fan_mode = FAN_MEDIUM
            elif msg["data2"] & 0xF0 == 48:
                self._attr_fan_mode = FAN_HIGH
            elif msg["data2"] & 0xF0 == 64:
                self._attr_fan_mode = FAN_AUTO
        elif msg["data1"] == 2:  # consigna
            self.target_temperature = msg["data2"] + 15
        elif msg["data1"] == 3:  # ambiente
            # double d = ((double) (164 - this.termostato.ambiente)) / 2.0d > 50.0d ? 0.0d : ((double) (164 - this.termostato.ambiente)) / 2.0d;
            if (164 - msg["data2"]) / 2 > 50:
                self.current_temperature = 0
            else:
                self.current_temperature = (164 - msg["data2"]) / 2
        elif msg["data1"] < 64 and msg["data2"] > 0:  # unknown values
            _LOGGER.info(
                f"Received unknown values from bus: data1={msg['data1']}, data2={msg['data2']}"
            )
            return False

        return True

    @property
    def address(self) -> int:
        return self._address

    @address.setter
    def address(self, address: int):
        self._address = address

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self._attr_name,
            manufacturer=ATTR_MANUFACTURER,
            model=None,
            via_device=(DOMAIN, self._parent_config_entry.entry_id),
        )

    @property
    def name(self):
        """Name of the entity."""
        return f"unit {self._unit}"

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        return "mdi:hvac" if self._is_on in [True, None] else "mdi:hvac-off"
