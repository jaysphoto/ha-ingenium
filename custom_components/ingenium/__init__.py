"""Ingenium integration package."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from typing import TypedDict

from .const import DOMAIN
from .device import Device, BUSDevice

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SWITCH]


class IngeniumConfigEntryData(TypedDict):
    host: str
    mac: str


class IngeniumRuntimeConfiguration(TypedDict):
    coordinator: Device
    devices: list[BUSDevice]


class IngeniumConfigEntry(ConfigEntry):
    """Data structure for Ingenium hass config entry"""

    data: IngeniumConfigEntryData
    runtime_configuration: IngeniumRuntimeConfiguration


async def async_setup_entry(hass: HomeAssistant, entry: IngeniumConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    coordinator = Device(hass, entry)
    await coordinator.async_initialize_device()

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": coordinator.get_devices(),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IngeniumConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if "coordinator" in entry.runtime_configuration:
        coordinator = entry.runtime_configuration["coordinator"]
        if coordinator.listener:
            coordinator.listener.cancel()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: IngeniumConfigEntry) -> None:
    """Reload the config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: IngeniumConfigEntry, device_entry: dr.DeviceEntry
):
    known_identifiers = entry.runtime_configuration[
        "coordinator"
    ].get_device_identifiers()

    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier in known_identifiers
    )
