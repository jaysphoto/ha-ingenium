"""Support for Ingenium AC gateway devices as CLIMATE platform types"""

from homeassistant.core import HomeAssistant
from homeassistant.const import UnitOfTemperature
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
    FAN_OFF,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_MANUFACTURER, DOMAIN, CONF_MAC
from .device import Device, BusDeviceType
from .entity import BaseEntity


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: dict,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Climate Device sensors."""

    # Add devices
    async_add_entities(
        [
            IngeniumClimate(
                config_entry,
                dev,
                ClimateEntityFeature(
                    ClimateEntityFeature.TARGET_TEMPERATURE
                    + ClimateEntityFeature.FAN_MODE
                ),
                "BUSing-LGAC-I",
            )
            for dev in config_entry.runtime_configuration["devices"]
            if dev.device_type in [BusDeviceType.AC_GATEWAY_LG]
        ]
    )


class IngeniumClimate(BaseEntity, ClimateEntity):
    def __init__(
        self,
        config_entry: dict,
        dev: Device,
        features: ClimateEntityFeature,
        model: str = None,
    ):
        super().__init__(config_entry, dev, model)

        self._unit_id = dev.output
        self._attr_has_entity_name = True
        self._attr_name = dev.label
        self._attr_unique_id = f"{config_entry.data.get(CONF_MAC)}_busing_{self._address}_unit_{self._unit_id}"
        self._attr_hvac_mode = None
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.AUTO,
            HVACMode.DRY,
            HVACMode.HEAT,
        ]
        if features | ClimateEntityFeature.FAN_MODE:
            self._attr_fan_mode = None
            self._attr_fan_modes = [FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
        if features | ClimateEntityFeature.TARGET_TEMPERATURE:
            self._attr_current_temperature = None
            self._attr_target_temperature = None
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_precision = 0.5
        self._attr_supported_features = features

    def _bus_message_filter(self, msg) -> bool:
        # Note: This type of device handles up to 63 units with 4 registers each:
        #   data1 == register(0-3) + self._unit_id * 4
        # Unit Id 0 = data1: 0-3
        # Unit Id 1 = data1: 4-7
        # ..
        # Unit Id 63 = data1: 252 - 255
        return msg["data1"] >= (self._unit_id * 4) and msg["data1"] < (
            self._unit_id * 4 + 4
        )

    def _read_bus_message(self, msg) -> bool:
        if msg["data1"] % 4 == 0:  # estado
            if msg["data2"] & 3 == 3:  # AC is ON
                self._attr_available = True
                self._attr_hvac_action = None
            elif msg["data2"] & 3 == 2:  # AC is OFF
                self._attr_available = True
                self._attr_hvac_action = HVACAction.OFF
            elif msg["data2"] & 3 == 0:  # AC controls unavailable
                self._attr_available = False
            else:
                # Skip UI update
                return False

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
            self._attr_target_temperature = msg["data2"] + 15
        elif msg["data1"] % 4 == 3:  # ambiente
            if (164 - msg["data2"]) / 2 > 50:
                return False

            self._attr_current_temperature = (164 - msg["data2"]) / 2

        return True

    # The device will report HVAC/Fan Mode, temperature setting even when OFF, therefor
    # we override some properties to None to prevent the device showing up in the UI
    # as if active.
    @property
    def hvac_mode(self) -> HVACMode | None:
        if self._attr_hvac_action == HVACAction.OFF:
            return HVACMode.OFF

        """Return hvac operation ie. heat, cool mode."""
        return self._attr_hvac_mode

    @property
    def current_temperature(self) -> float | None:
        if self._attr_hvac_action == HVACAction.OFF:
            return None

        """Return the current temperature."""
        return self._attr_current_temperature

    @property
    def target_temperature(self) -> float | None:
        if self._attr_hvac_action == HVACAction.OFF:
            return None

        """Return the temperature we try to reach."""
        return self._attr_target_temperature
