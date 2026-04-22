import pytest

from unittest.mock import MagicMock, Mock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ingenium import switch as ingenium_switch
from custom_components.ingenium.const import ATTR_MANUFACTURER, DOMAIN
from custom_components.ingenium.device import BusDeviceType, BUSDevice


@pytest.fixture
def device_1() -> BUSDevice:
    return BUSDevice(
        address=1,
        label="Output 4",
        device_type=BusDeviceType.ACTUATOR_ALL_NOTHING,
        type=24,
        output=4,
    )


@pytest.fixture
def device_2() -> BUSDevice:
    return BUSDevice(
        address=1,
        label="Output 5",
        device_type=BusDeviceType.ACTUATOR_ALL_NOTHING,
        type=24,
        output=5,
    )


async def test_async_setup_entry_adds_binary_switch_entities(hass, device_1, device_2):
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    coordinator = Mock()
    coordinator.data = {}
    coordinator.async_add_listener = MagicMock(return_value=None)
    coordinator.async_remove_listener = MagicMock(return_value=None)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [device_1, device_2],
    }

    async_add_entities = MagicMock()

    await ingenium_switch.async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    added_entities = async_add_entities.call_args[0][0]

    assert len(added_entities) == 2
    assert {entity._output for entity in added_entities} == {4, 5}
    assert all(entity._address == 1 for entity in added_entities)
    assert all(entity._model == "2E2S/2E2S-30A" for entity in added_entities)
    assert {entity.unique_id for entity in added_entities} == {
        "A123B_busing_1_4",
        "A123B_busing_1_5",
    }
    assert {entity.name.startswith("Output ") for entity in added_entities}
    assert added_entities[1].device_info == added_entities[0].device_info


async def test_ingenium_binary_switch_device_info(hass, device_1):
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    coordinator = Mock()
    coordinator.data = {}
    coordinator.async_add_listener = MagicMock(return_value=None)
    coordinator.async_remove_listener = MagicMock(return_value=None)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_switch.IngeniumBinarySwitch(entry, device_1, model="2E2S")

    assert entity.device_info["identifiers"] == {(DOMAIN, "A123B", 1)}
    assert entity.device_info["name"] == "smart_touch_A123B_1"
    assert entity.device_info["manufacturer"] == ATTR_MANUFACTURER
    assert entity.device_info["model"] == "2E2S"
    assert entity.device_info["via_device"] == (DOMAIN, "A123B")


async def test_ingenium_binary_switch_updates_state(hass, device_1):
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    coordinator = Mock()
    coordinator.data = {}
    coordinator.async_add_listener = MagicMock(return_value=None)
    coordinator.async_remove_listener = MagicMock(return_value=None)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_switch.IngeniumBinarySwitch(entry, device_1, model="2E2S")
    entity.async_write_ha_state = MagicMock()

    # Construct BUSing message of activating the output
    coordinator.data = {
        1: {
            "bus_messages": [
                {"command": 4, "data1": 2, "data2": device_1.output},
            ]
        }
    }
    entity._handle_coordinator_update()

    assert entity.is_on is True
    entity.async_write_ha_state.assert_called_once()

    entity.async_write_ha_state.reset_mock()

    # Construct BUSing response message of deactivating the output
    coordinator.data = {
        1: {
            "bus_messages": [
                {"command": 4, "data1": 2, "data2": (device_1.output + 8)},
            ]
        }
    }
    entity._handle_coordinator_update()

    assert entity.is_on is False
    entity.async_write_ha_state.assert_called_once()

    entity.async_write_ha_state.reset_mock()

    # Construct BUSing response message for another output
    coordinator.data = {
        1: {
            "bus_messages": [
                {"command": 4, "data1": 2, "data2": (device_1.output + 1)},
            ]
        }
    }
    entity._handle_coordinator_update()

    entity.async_write_ha_state.assert_not_called()


async def test_ingenium_binary_switch_read_outputs(hass, device_1):
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    coordinator = Mock()
    coordinator.data = {}
    coordinator.async_add_listener = MagicMock(return_value=None)
    coordinator.async_remove_listener = MagicMock(return_value=None)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_switch.IngeniumBinarySwitch(entry, device_1, model="2E2S")
    entity.async_write_ha_state = MagicMock()

    # Construct BUSing message where all outputs are off
    coordinator.data = {
        1: {
            "bus_messages": [
                {"command": 4, "data1": 1, "data2": 0},
            ]
        }
    }
    entity._handle_coordinator_update()

    assert entity.is_on is False
    entity.async_write_ha_state.assert_called_once()
    entity.async_write_ha_state.reset_mock()

    # Construct BUSing message where only output 4 is on
    coordinator.data = {
        1: {
            "bus_messages": [
                {"command": 4, "data1": 1, "data2": 16},
            ]
        }
    }
    entity._handle_coordinator_update()

    assert entity.is_on is True
    entity.async_write_ha_state.assert_called_once()
    entity.async_write_ha_state.reset_mock()

    # Construct BUSing message where only output 5 is on
    coordinator.data = {
        1: {
            "bus_messages": [
                {"command": 4, "data1": 1, "data2": 32},
            ]
        }
    }
    entity._handle_coordinator_update()

    assert entity.is_on is False
    entity.async_write_ha_state.assert_called_once()
    entity.async_write_ha_state.reset_mock()

    # Construct BUSing message where output 4+5 are on
    coordinator.data = {
        1: {
            "bus_messages": [
                {"command": 4, "data1": 1, "data2": 48},
            ]
        }
    }
    entity._handle_coordinator_update()

    assert entity.is_on is True
    entity.async_write_ha_state.assert_called_once()
