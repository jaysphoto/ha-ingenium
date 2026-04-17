"""Basic tests for the Ingenium integration."""

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ingenium import Device
from custom_components.ingenium.device import BUSDevice
from custom_components.ingenium.const import (
    DOMAIN,
    CONF_IGNORE_AVAILABILITY,
    CONF_INSTALLATION_DATA,
    CONF_DEVICE,
)


def test_device_init(hass):
    hass.data.setdefault(DOMAIN, {})

    config_data = {"mac": "A123B", "host": "192.168.1.100"}

    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    dev = Device(hass, entry)

    devices = dev.get_devices()

    # BUSing device list empty
    assert type(devices) is list
    assert not devices


@pytest.mark.asyncio
async def test_with_async_init(hass):
    hass.data.setdefault(DOMAIN, {})

    config_data = {"mac": "A123B", "host": "192.168.1.100"}

    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    dev = Device(hass, entry)
    result = await dev.async_initialize_device()

    assert result is None


def test_device_init_with_bus_devices(hass):
    hass.data.setdefault(DOMAIN, {})

    config_data = {
        "mac": "A123B",
        "host": "192.168.1.100",
        CONF_DEVICE: {
            CONF_INSTALLATION_DATA: [
                {"label": "GENERAL", "type": 47, "output": 0, "address": 1},
                {"label": "INTRUSION ON", "type": 26, "output": 0, "address": 2},
                {"label": "INTRUSION OFF", "type": 26, "output": 0, "address": 6},
            ]
        },
    }

    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    dev = Device(hass, entry)

    devices = dev.get_devices()

    # BUSing device list empty
    assert type(devices) is list
    assert all(isinstance(d, BUSDevice) for d in devices)
    assert len(devices) == 3
    assert type(devices[0]) is BUSDevice

    assert devices[0].label == "GENERAL"
    assert devices[0].type == 47
    assert devices[0].device_type.name == "AC_GATEWAY_LG"
    assert devices[0].device_type.value == 47

    assert devices[1].label == "INTRUSION ON"
    assert devices[1].type == 26
    assert devices[1].device_type.name == "OTHER"
    assert devices[1].device_type.value == 0


def test_device_init_with_bus_devices_ignored(hass):
    hass.data.setdefault(DOMAIN, {})

    config_data = {
        "mac": "A123B",
        "host": "192.168.1.100",
        CONF_DEVICE: {
            CONF_INSTALLATION_DATA: [
                {"label": "GENERAL", "type": 47, "output": 0, "address": 1},
                {"label": "INTRUSION ON", "type": 26, "output": 0, "address": 2},
                {"label": "INTRUSION OFF", "type": 26, "output": 0, "address": 6},
            ]
        },
        CONF_IGNORE_AVAILABILITY: [{"type": 26, "output": 0, "address": 2}],
    }

    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    dev = Device(hass, entry)

    devices = dev.get_devices()

    # BUSing device list with 2 items, 'INTRUSION ON' was ignored
    assert type(devices) is list
    assert len(devices) == 2
    assert len([d for d in devices if d.label == "INTRUSION ON"]) == 0
