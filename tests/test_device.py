"""Basic tests for the Ingenium integration."""

import pytest
from unittest.mock import patch, Mock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ingenium import Device
from custom_components.ingenium.device import BUSDevice
from custom_components.ingenium.const import (
    DOMAIN,
    CONF_IGNORE_AVAILABILITY,
    CONF_INSTALLATION_DATA,
    CONF_DEVICE,
    TASK_BUSING,
)


@pytest.fixture
def dev(hass):
    hass.data.setdefault(DOMAIN, {})

    config_data = {"mac": "A123B", "host": "192.168.1.100"}
    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    return Device(hass, entry)


def test_device_init(dev):
    """Test initialization of Device with basic config and no BUSing devices."""
    devices = dev.get_devices()

    # BUSing device list empty
    assert type(devices) is list
    assert not devices


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


@pytest.mark.asyncio
async def test_with_async_init(hass, dev):
    """ "Test that async initialization of the device sets up the communication and listener."""
    hass.data.setdefault(DOMAIN, {})

    config_data = {"mac": "A123B", "host": "192.168.1.100"}
    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    with (
        patch.object(hass, "async_create_background_task") as mock_create_task,
    ):
        dev = Device(hass, entry)

        # Patch the device Comms to avoid real network calls and to verify listener setup
        dev._comm = Mock(listener=Mock())

        result = await dev.async_initialize_device()

        assert result is None
        assert mock_create_task.call_count == 1
        assert mock_create_task.call_args[0][1] == f"{DOMAIN}_{TASK_BUSING}"


def test_bus_message_register_write(dev):
    """Test handling of BUS message with command 1 (register write) and origin 0xFEFE."""
    with patch.object(dev, "async_set_updated_data") as mock_set_data:
        address = 5
        msgs = [
            {
                "command": 4,
                "origin": 0xFEFE,
                "destination": address,
                "data1": 0x01,
                "data2": 0x02,
            }
        ]
        dev._bus_message(msgs)

        mock_set_data.assert_called_once()
        call_args = mock_set_data.call_args[0][0]
        assert address in call_args
        assert call_args[address]["bus_messages"][0]["command"] == 4


def test_bus_message_ack_nack(dev):
    """Test handling of BUS message with command 1 (ACK message)."""
    with patch.object(dev, "async_set_updated_data") as mock_set_data:
        address = 10
        msgs = [
            {
                "command": 1,
                "origin": address,
                "destination": 0xFEFE,
                "data1": 0x01,
                "data2": 0x02,
            },
            {
                "command": 2,
                "origin": address,
                "destination": 0xFEFE,
                "data1": 0x01,
                "data2": 0x02,
            },
        ]
        dev._bus_message(msgs)

        mock_set_data.assert_not_called()


def test_bus_message_self_reported(dev):
    """Test handling of BUS message with command 4 (self-reported value change)."""
    with patch.object(dev, "async_set_updated_data") as mock_set_data:
        address = 7
        msgs = [
            {
                "command": 4,
                "origin": address,
                "destination": address,
                "data1": 0xFF,
                "data2": 0x00,
            }
        ]
        dev._bus_message(msgs)

        mock_set_data.assert_called_once()
        call_args = mock_set_data.call_args[0][0]
        assert address in call_args
        assert call_args[address]["bus_messages"][0]["command"] == 4


def test_bus_message_request_dump_ignored(dev):
    """Test that request message (command 10) is ignored."""
    with patch.object(dev, "async_set_updated_data") as mock_set_data:
        msgs = [
            {
                "command": 10,
                "origin": 0xFEFE,
                "destination": 0xFFFF,
                "data1": 0,
                "data2": 0,
            }
        ]
        dev._bus_message(msgs)

        mock_set_data.assert_not_called()


def test_bus_message_multiple_messages(dev):
    """Test handling of multiple BUS messages with different contexts."""
    with patch.object(dev, "async_set_updated_data") as mock_set_data:
        msgs = [
            {
                "command": 10,
                "origin": 0xFEFE,
                "destination": 0xFFFF,
                "data1": 0,
                "data2": 0,
            },  # Ignored message
            {
                "command": 4,
                "origin": 0xFEFE,
                "destination": 5,
                "data1": 0x01,
                "data2": 0x00,
            },
            {"command": 4, "origin": 7, "destination": 7, "data1": 0xFF, "data2": 0xFF},
            {
                "command": 4,
                "origin": 0xFEFE,
                "destination": 5,
                "data1": 0x02,
                "data2": 0x00,
            },
        ]
        dev._bus_message(msgs)

        mock_set_data.assert_called_once()
        call_args = mock_set_data.call_args[0][0]
        # Two contexts: 5 and 7
        assert len(call_args) == 2
        assert 5 in call_args
        assert 7 in call_args
        # Context 5 should have 2 messages
        assert len(call_args[5]["bus_messages"]) == 2
        # Context 7 should have 1 message
        assert len(call_args[7]["bus_messages"]) == 1


def test_bus_message_all_ignored(dev):
    """Test ignoring of unknown bus messages"""
    with patch.object(dev, "async_set_updated_data") as mock_set_data:
        msgs = [
            {
                "command": 1,
                "origin": 0xFEFE,
                "destination": 5,
                "data1": 0x00,
                "data2": 0x00,
            },
            {
                "command": 10,
                "origin": 0xFEFE,
                "destination": 0xFFFF,
                "data1": 0,
                "data2": 0,
            },
            {"command": 99, "origin": 15, "destination": 20, "data1": 0x01, "data2": 0},
            {"command": 50, "origin": 3, "destination": 8, "data1": 0xFF, "data2": 0},
        ]
        dev._bus_message(msgs)

        mock_set_data.assert_not_called()
