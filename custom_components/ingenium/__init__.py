"""Ingenium integration package."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .device import Device

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    coordinator = Device(hass, entry)
    await coordinator.async_initialize_device()

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": coordinator.get_devices(),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
