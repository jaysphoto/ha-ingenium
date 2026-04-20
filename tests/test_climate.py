from unittest.mock import MagicMock, Mock

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.components.climate.const import (
    HVACMode,
    FAN_OFF,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ingenium import climate as ingenium_climate
from custom_components.ingenium.const import (
    ATTR_MANUFACTURER,
    DOMAIN,
    CONF_MAC,
    CONF_HOST,
)
from custom_components.ingenium.device import BusDeviceType, BUSDevice


async def test_async_setup_entry_adds_climate_entities(hass):
    """Test that async_setup_entry adds climate entities for AC gateway devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: "A123B", CONF_HOST: "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    coordinator = Mock()
    coordinator.data = {}
    coordinator.async_add_listener = MagicMock(return_value=None)
    coordinator.async_remove_listener = MagicMock(return_value=None)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [
            BUSDevice(
                address=5,
                label="Living Room AC",
                device_type=BusDeviceType.AC_GATEWAY_LG,
                type=47,
                output=0,
            ),
            BUSDevice(
                address=5,
                label="Bedroom AC",
                device_type=BusDeviceType.AC_GATEWAY_LG,
                type=47,
                output=1,
            ),
        ],
    }

    async_add_entities = MagicMock()

    await ingenium_climate.async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    added_entities = async_add_entities.call_args[0][0]

    # Only AC gateway devices should be added, not actuators
    assert len(added_entities) == 2
    assert {entity._address for entity in added_entities} == {5, 5}
    assert {entity.unique_id for entity in added_entities} == {
        "A123B_busing_5_unit_0",
        "A123B_busing_5_unit_1",
    }
    assert {added_entities[0].device_info == added_entities[1].device_info}


async def test_ingenium_climate_entity_initialization_and_attributes(hass):
    """Test IngeniumClimate entity initialization and default attributes."""
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

    entity = ingenium_climate.IngeniumClimate(
        entry, address=5, unit_id=0, label="Living Room AC"
    )

    # Check initialization
    assert entity.unique_id == "A123B_busing_5_unit_0"
    assert entity.name == "Living Room AC"
    assert entity.temperature_unit == "°C"
    assert entity.precision == 0.5
    assert entity.hvac_mode == HVACMode.OFF
    assert set(entity.hvac_modes) == {
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.OFF,
    }
    assert set(entity.fan_modes) == {FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH}
    assert entity.fan_mode is None


async def test_ingenium_climate_device_info(hass):
    """Test IngeniumClimate device info."""
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

    entity = ingenium_climate.IngeniumClimate(entry, address=5, unit_id=0)

    device_info = entity.device_info
    assert device_info["identifiers"] == {(DOMAIN, 5)}
    assert device_info["name"] == "LG-I 5"
    assert device_info["manufacturer"] == ATTR_MANUFACTURER
    assert device_info["model"] == "BUSing-LGAC-I"
    assert device_info["via_device"] == (DOMAIN, entry.entry_id)


async def test_ingenium_climate_ac_state_on_off_unavailable(hass):
    """Test AC state parsing (ON/OFF/UNAVAILABLE) from bus messages."""
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

    entity = ingenium_climate.IngeniumClimate(entry, address=5, unit_id=0)
    entity.async_write_ha_state = MagicMock()

    # AC ON (data2 & 3 == 3)
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 0, "data2": 0x03},  # AC ON
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity._attr_state == STATE_ON
    entity.async_write_ha_state.assert_called_once()

    # AC OFF (data2 & 3 == 2)
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 0, "data2": 0x02},  # AC OFF
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity._attr_state == STATE_OFF
    entity.async_write_ha_state.assert_called_once()

    # AC UNAVAILABLE (data2 & 3 == 0)
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 0, "data2": 0x00},  # AC UNAVAILABLE
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity._attr_state == STATE_UNAVAILABLE
    entity.async_write_ha_state.assert_called_once()


async def test_ingenium_climate_mode_and_fan_parsing(hass):
    """Test HVAC mode and fan mode parsing from operation mode register."""
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

    entity = ingenium_climate.IngeniumClimate(entry, address=5, unit_id=0)
    entity.async_write_ha_state = MagicMock()

    # Test: Fan OFF + HVAC OFF (data2 < 16)
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 1, "data2": 0x00},
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity._attr_fan_mode == FAN_OFF
    assert entity._attr_hvac_mode == HVACMode.OFF
    entity.async_write_ha_state.assert_called_once()

    # Test: Fan LOW + HVAC COOL (data2 = 0x10 | 0x00)
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 1, "data2": 0x10},  # FAN_LOW + COOL
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity._attr_fan_mode == FAN_LOW
    assert entity._attr_hvac_mode == HVACMode.COOL
    entity.async_write_ha_state.assert_called_once()

    # Test: Fan MEDIUM + HVAC DRY (data2 = 0x20 | 0x01)
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 1, "data2": 0x21},  # FAN_MEDIUM + DRY
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity._attr_fan_mode == FAN_MEDIUM
    assert entity._attr_hvac_mode == HVACMode.DRY
    entity.async_write_ha_state.assert_called_once()

    # Test: Fan HIGH + HVAC FAN_ONLY (data2 = 0x30 | 0x02)
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 1, "data2": 0x32},  # FAN_HIGH + FAN_ONLY
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity._attr_fan_mode == FAN_HIGH
    assert entity._attr_hvac_mode == HVACMode.FAN_ONLY
    entity.async_write_ha_state.assert_called_once()

    # Test: Fan AUTO + HVAC AUTO (data2 = 0x40 | 0x03)
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 1, "data2": 0x43},  # FAN_AUTO + AUTO
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity._attr_fan_mode == FAN_AUTO
    assert entity._attr_hvac_mode == HVACMode.AUTO
    entity.async_write_ha_state.assert_called_once()

    # Test: HVAC HEAT (data2 = 0x10 | 0x04)
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 1, "data2": 0x14},  # FAN_LOW + HEAT
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity._attr_hvac_mode == HVACMode.HEAT
    entity.async_write_ha_state.assert_called_once()


async def test_ingenium_climate_target_temperature(hass):
    """Test target temperature parsing from register."""
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

    entity = ingenium_climate.IngeniumClimate(entry, address=5, unit_id=0)
    entity.async_write_ha_state = MagicMock()

    # Target temp = data2 + 15, e.g., data2=10 -> 25°C
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 2, "data2": 10},
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity.target_temperature == 25
    entity.async_write_ha_state.assert_called_once()

    # Test another value: data2=5 -> 20°C
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 2, "data2": 5},
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity.target_temperature == 20
    entity.async_write_ha_state.assert_called_once()


async def test_ingenium_climate_current_temperature(hass):
    """Test current temperature parsing from environment register."""
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

    entity = ingenium_climate.IngeniumClimate(entry, address=5, unit_id=0)
    entity.async_write_ha_state = MagicMock()

    # Current temp = (164 - data2) / 2, e.g., data2=114 -> 25°C
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 3, "data2": 114},
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity.current_temperature == 25
    entity.async_write_ha_state.assert_called_once()

    # Test another value: data2=144 -> 10°C
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 3, "data2": 144},
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity.current_temperature == 10
    entity.async_write_ha_state.assert_called_once()

    # Test temperature > 50°C sets to 0 (sensor error)
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {
        5: {
            "bus_messages": [
                # (164 - 63) / 2 = 50.5
                {"command": 4, "data1": 3, "data2": 63},
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity.current_temperature == 0
    entity.async_write_ha_state.assert_called_once()


async def test_ingenium_climate_ignores_out_of_range_registers(hass):
    """Test that entity correctly filters messages based on register range for unit_id."""
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

    # Unit ID 0 (registers 0-3)
    entity = ingenium_climate.IngeniumClimate(entry, address=5, unit_id=0)
    entity.async_write_ha_state = MagicMock()

    # Messages in range [0, 4) should be processed
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 0, "data2": 0x03},  # In range
                {"command": 4, "data1": 1, "data2": 0x10},  # In range
            ]
        }
    }
    entity._handle_coordinator_update()
    assert entity._attr_state == STATE_ON
    assert entity._attr_fan_mode == FAN_LOW
    entity.async_write_ha_state.assert_called_once()

    # Reset and test messages outside range [0, 4) are NOT processed
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 4, "data2": 0x03},  # Outside range
                {"command": 4, "data1": 5, "data2": 0x10},  # Outside range
            ]
        }
    }
    entity._handle_coordinator_update()
    # State should not change since data1 values are outside this unit's range
    entity.async_write_ha_state.assert_not_called()


async def test_ingenium_climate_ignores_missing_address(hass):
    """Test that entity gracefully handles missing address in coordinator data."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    coordinator = Mock()
    coordinator.data = {6: {"bus_messages": []}}  # Different address
    coordinator.async_add_listener = MagicMock(return_value=None)
    coordinator.async_remove_listener = MagicMock(return_value=None)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_climate.IngeniumClimate(entry, address=5, unit_id=0)
    entity.async_write_ha_state = MagicMock()

    # Should not raise exception and should not update state
    entity._handle_coordinator_update()
    entity.async_write_ha_state.assert_not_called()


async def test_ingenium_climate_multiple_messages_in_update(hass):
    """Test handling multiple bus messages in a single coordinator update."""
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

    entity = ingenium_climate.IngeniumClimate(entry, address=5, unit_id=0)
    entity.async_write_ha_state = MagicMock()

    # Multiple messages in one update
    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 0, "data2": 0x03},  # AC ON
                {"command": 4, "data1": 1, "data2": 0x43},  # FAN_AUTO + AUTO
                {"command": 4, "data1": 2, "data2": 10},  # Target 25°C
                {"command": 4, "data1": 3, "data2": 114},  # Current 25°C
            ]
        }
    }
    entity._handle_coordinator_update()

    # All state should be updated
    assert entity._attr_state == STATE_ON
    assert entity._attr_hvac_mode == HVACMode.AUTO
    assert entity._attr_fan_mode == FAN_AUTO
    assert entity.target_temperature == 25
    assert entity.current_temperature == 25
    # async_write_ha_state should be called once for the update
    entity.async_write_ha_state.assert_called_once()
