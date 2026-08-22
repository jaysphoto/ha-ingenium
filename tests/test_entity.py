import pytest

from unittest.mock import AsyncMock, MagicMock, Mock

from custom_components.ingenium.const import (
    ATTR_MANUFACTURER,
    DOMAIN,
    CONF_MAC,
    CONF_HOST,
)
from custom_components.ingenium.device import BusDeviceType, BUSDevice
from custom_components.ingenium.entity import BaseEntity

from homeassistant.helpers.entity import DeviceInfo, Entity

from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture
def coordinator():
    """Create a coordinator mock with the listener and comm hooks used by entities."""
    mock = Mock()
    mock.data = {}
    mock.async_add_listener = MagicMock(return_value=None)
    mock.async_remove_listener = MagicMock(return_value=None)
    mock.comm = Mock()
    mock.comm.send_message = AsyncMock()

    return mock


@pytest.fixture
def device() -> BUSDevice:
    return BUSDevice(
        address=11,
        label="Living Room AC",
        device_type=BusDeviceType.AC_GATEWAY_LG,
        output=0,
        type=47,
    )


@pytest.mark.asyncio
async def test_entity_setup(hass, device, coordinator):
    """Test that the Ingenium entity is set up correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: "A123B", CONF_HOST: "192.168.1.100"},
    )
    entry.add_to_hass(hass)
    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    # Create an instance of the BaseEntity
    entity = BaseEntity(config_entry=entry, dev=device)

    assert isinstance(entity, BaseEntity)
    assert isinstance(entity, Entity)


async def test_ingenium_climate_device_info(hass, coordinator, device):
    """Test IngeniumClimate device info."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    model = "test_model"
    entity = BaseEntity(
        config_entry=entry,
        dev=device,
        model=model,
    )

    device_info = entity.device_info

    assert device_info["identifiers"] == {(DOMAIN, "A123B", 11, 47)}
    assert device_info["name"] == "smart_touch_A123B_11"
    assert device_info["manufacturer"] == ATTR_MANUFACTURER
    assert device_info["model"] == model
    assert device_info["via_device"] == (DOMAIN, "A123B")


async def test_bus_message_processing(hass, device, coordinator):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: "A123B", CONF_HOST: "192.168.1.100"},
    )
    entry.add_to_hass(hass)
    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    # Create an instance of the BaseEntity
    entity = BaseEntity(config_entry=entry, dev=device)
    entity.async_write_ha_state = AsyncMock()

    # Simulate a coordinator update
    entity.coordinator.data = {
        device.address: {
            "bus_messages": [
                {"command": 4, "data1": 0, "data2": 0},
                {"command": 4, "data1": 1, "data2": 0},
            ]
        }
    }
    entity._handle_coordinator_update()

    # HA state should be updated since the bus messages processing is a 'pass' (do nothing) by default
    entity.async_write_ha_state.assert_not_called()


@pytest.mark.asyncio
async def test_entity_send_message(hass, device, coordinator):
    """Test Sending Ingenium BUSing messages."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: "A123B", CONF_HOST: "192.168.1.100"},
    )
    entry.add_to_hass(hass)
    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    # Create an instance of the BaseEntity and await sending the BUSing message
    entity = BaseEntity(config_entry=entry, dev=device)
    await entity._send_bus_message(command=4, data1=1, data2=2)

    coordinator.comm.send_message.assert_awaited_once_with(
        destination=11,
        command=4,
        data1=1,
        data2=2,
        cb=entity._process_response_message,
    )
