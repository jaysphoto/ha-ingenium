"""Ingenium integration package."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, TASK_BUSING
from .device import Device

PLATFORMS: list[Platform] = [Platform.CLIMATE]


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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data and TASK_BUSING in data:
        data[TASK_BUSING].cancel()

        try:
            await data[TASK_BUSING]
        except BaseException:
            pass

    return True
