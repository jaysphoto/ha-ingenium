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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MAC
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
                    | ClimateEntityFeature.FAN_MODE
                    | ClimateEntityFeature.TURN_ON
                    | ClimateEntityFeature.TURN_OFF
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
        # Device features are set based on the device type, but we can override them here if needed
        self._attr_supported_features = features

        if features | ClimateEntityFeature.FAN_MODE:
            self._attr_fan_mode = None
            self._attr_fan_modes = [FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
        if features | ClimateEntityFeature.TARGET_TEMPERATURE:
            self._attr_current_temperature = None
            self._attr_target_temperature = None
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_precision = 0.5

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

    def set_fan_mode(self, fan_mode: str) -> None:
        self.hass.async_create_task(self.async_set_fan_mode(fan_mode))

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        self.hass.async_create_task(self.async_set_hvac_mode(hvac_mode))

    async def async_turn_on(self) -> None:
        """Turn the AC on."""
        await self._send_bus_message(command=4, data1=(self._unit_id * 4), data2=3)

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        await self._send_bus_message(command=4, data1=(self._unit_id * 4), data2=2)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode == FAN_OFF:
            fan_mode_data2 = 0
        elif fan_mode == FAN_LOW:
            fan_mode_data2 = 16
        elif fan_mode == FAN_MEDIUM:
            fan_mode_data2 = 32
        elif fan_mode == FAN_HIGH:
            fan_mode_data2 = 48
        elif fan_mode == FAN_AUTO:
            fan_mode_data2 = 64
        else:
            return

        # Set HVAC MODE bits based on current state, or default to COOL if not set
        if self._attr_hvac_mode == HVACMode.COOL:
            hvac_mode_data2 = 0
        elif self._attr_hvac_mode == HVACMode.DRY:
            hvac_mode_data2 = 1
        elif self._attr_hvac_mode == HVACMode.FAN_ONLY:
            hvac_mode_data2 = 2
        elif self._attr_hvac_mode == HVACMode.AUTO:
            hvac_mode_data2 = 3
        elif self._attr_hvac_mode == HVACMode.HEAT:
            hvac_mode_data2 = 4
        else:
            hvac_mode_data2 = 0

        await self._send_bus_message(
            command=4,
            data1=(self._unit_id * 4) + 1,
            data2=hvac_mode_data2 | fan_mode_data2,
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self._write_mode_register(
            hvac_mode=self._attr_hvac_mode, fan_mode=fan_mode
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self._write_mode_register(
                hvac_mode=hvac_mode, fan_mode=self._attr_fan_mode
            )

            # Turn on the AC unit if it is currently OFF
            if self._attr_hvac_action == HVACAction.OFF:
                await self.async_turn_on()

    async def _write_mode_register(self, hvac_mode: HVACMode, fan_mode: str) -> None:
        # Set FAN MODE bits based on current state, or default to FAN_OFF if not set
        if fan_mode == FAN_LOW:
            fan_mode_data2 = 16
        elif fan_mode == FAN_MEDIUM:
            fan_mode_data2 = 32
        elif fan_mode == FAN_HIGH:
            fan_mode_data2 = 48
        elif fan_mode == FAN_AUTO:
            fan_mode_data2 = 64
        else:
            fan_mode_data2 = 0

        # Set HVAC MODE bits based on requested mode
        if hvac_mode == HVACMode.COOL:
            hvac_mode_data2 = 0
        elif hvac_mode == HVACMode.DRY:
            hvac_mode_data2 = 1
        elif hvac_mode == HVACMode.FAN_ONLY:
            hvac_mode_data2 = 2
        elif hvac_mode == HVACMode.AUTO:
            hvac_mode_data2 = 3
        elif hvac_mode == HVACMode.HEAT:
            hvac_mode_data2 = 4
        else:
            hvac_mode_data2 = 0

        await self._send_bus_message(
            command=4,
            data1=(self._unit_id * 4) + 1,
            data2=hvac_mode_data2 | fan_mode_data2,
        )

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
