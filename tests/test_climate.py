import pytest

from unittest.mock import AsyncMock, MagicMock, Mock

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
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ingenium import climate as ingenium_climate, entity
from custom_components.ingenium.const import (
    ATTR_MANUFACTURER,
    DOMAIN,
    CONF_MAC,
    CONF_HOST,
)
from custom_components.ingenium.device import BusDeviceType, BUSDevice


@pytest.fixture
def device_1() -> BUSDevice:
    return BUSDevice(
        address=5,
        label="Living Room AC",
        device_type=BusDeviceType.AC_GATEWAY_LG,
        output=0,
        type=47,
    )


@pytest.fixture
def device_2() -> BUSDevice:
    return BUSDevice(
        address=5,
        label="Bedroom AC",
        device_type=BusDeviceType.AC_GATEWAY_LG,
        output=1,
        type=47,
    )


@pytest.fixture
def features() -> ClimateEntityFeature:
    return ClimateEntityFeature(
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )


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


async def test_async_setup_entry_adds_climate_entities(
    hass, device_1, device_2, coordinator
):
    """Test that async_setup_entry adds climate entities for AC gateway devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: "A123B", CONF_HOST: "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [device_1, device_2],
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


async def test_ingenium_climate_entity_initialization_and_attributes(
    hass, device_1, features, coordinator
):
    """Test IngeniumClimate entity initialization and default attributes."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_climate.IngeniumClimate(entry, device_1, features)

    # Check initialization
    assert entity.unique_id == "A123B_busing_5_unit_0"
    assert entity.name == "Living Room AC"
    assert entity.temperature_unit == "°C"
    assert entity.precision == 0.5
    assert entity.hvac_mode == None
    assert set(entity.hvac_modes) == {
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.OFF,
    }
    assert set(entity.fan_modes) == {FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH}
    assert entity.fan_mode is None


async def test_ingenium_climate_device_info(hass, device_1, features, coordinator):
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

    model = "BUSing-LGAC-I"
    entity = ingenium_climate.IngeniumClimate(entry, device_1, features, model)

    device_info = entity.device_info
    assert device_info["identifiers"] == {(DOMAIN, "A123B", 5, 47)}
    assert device_info["name"] == "smart_touch_A123B_5"
    assert device_info["manufacturer"] == ATTR_MANUFACTURER
    assert device_info["model"] == model
    assert device_info["via_device"] == (DOMAIN, "A123B")


async def test_ingenium_climate_ac_state_on_off_unavailable(
    hass, device_1, features, coordinator
):
    """Test AC state parsing (ON/OFF/UNAVAILABLE) from bus messages."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_climate.IngeniumClimate(entry, device_1, features)
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
    assert entity._attr_available is True
    assert entity._attr_hvac_action is None
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
    assert entity._attr_available is True
    assert entity._attr_hvac_action is HVACAction.OFF
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
    assert entity._attr_available == False
    entity.async_write_ha_state.assert_called_once()


async def test_ingenium_climate_mode_and_fan_parsing(
    hass, device_1, features, coordinator
):
    """Test HVAC mode and fan mode parsing from operation mode register."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_climate.IngeniumClimate(entry, device_1, features)
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


async def test_ingenium_climate_target_temperature(
    hass, device_1, features, coordinator
):
    """Test target temperature parsing from register."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_climate.IngeniumClimate(entry, device_1, features)
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


async def test_ingenium_climate_current_temperature(
    hass, device_1, features, coordinator
):
    """Test current temperature parsing from environment register."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_climate.IngeniumClimate(entry, device_1, features)
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
    assert entity.current_temperature == 10  # previous valid value
    entity.async_write_ha_state.assert_not_called()


async def test_ingenium_climate_ignores_out_of_range_registers(
    hass, device_1, features, coordinator
):
    """Test that entity correctly filters messages based on register range for unit_id."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    # Unit ID 0 (registers 0-3)
    entity = ingenium_climate.IngeniumClimate(entry, device_1, features)
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
    assert entity._attr_hvac_action == None
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


async def test_ingenium_climate_ignores_missing_address(
    hass, device_1, features, coordinator
):
    """Test that entity gracefully handles missing address in coordinator data."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    coordinator.data = {6: {"bus_messages": []}}  # Different address

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_climate.IngeniumClimate(entry, device_1, features)
    entity.async_write_ha_state = MagicMock()

    # Should not raise exception and should not update state
    entity._handle_coordinator_update()
    entity.async_write_ha_state.assert_not_called()


async def test_ingenium_climate_multiple_messages_in_update(
    hass, device_1, features, coordinator
):
    """Test handling multiple bus messages in a single coordinator update."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_climate.IngeniumClimate(entry, device_1, features)
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
    assert entity._attr_hvac_action == None
    assert entity._attr_hvac_mode == HVACMode.AUTO
    assert entity._attr_fan_mode == FAN_AUTO
    assert entity.target_temperature == 25
    assert entity.current_temperature == 25
    # async_write_ha_state should be called once for the update
    entity.async_write_ha_state.assert_called_once()


async def test_ingenium_climate_off_mode(hass, device_1, features, coordinator):
    """Test handling multiple bus messages in a single coordinator update."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_climate.IngeniumClimate(entry, device_1, features)
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
    entity.async_write_ha_state.reset_mock()

    coordinator.data = {
        5: {
            "bus_messages": [
                {"command": 4, "data1": 0, "data2": 0x02},  # AC OFF
            ]
        }
    }
    entity._handle_coordinator_update()

    # All state should be updated
    assert entity._attr_hvac_action == HVACAction.OFF
    assert entity._attr_hvac_mode == HVACMode.AUTO  # Internal state is still stored
    # .. mode reports as "OFF", because the AC is OFF
    assert entity.hvac_mode == HVACMode.OFF
    assert entity.fan_mode == FAN_AUTO
    assert entity.target_temperature == None  # These are hidden as well
    assert entity.current_temperature == None  # These are hidden as well

    # async_write_ha_state should be called once for the update
    entity.async_write_ha_state.assert_called_once()


@pytest.mark.asyncio
async def test_ingenium_climate_on_off_controls(hass, device_1, features, coordinator):
    """Test on/off control send payloads and response handling for ACK/NACK messages."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_climate.IngeniumClimate(entry, device_1, features)
    entity.async_write_ha_state = MagicMock()
    entity._attr_available = False
    entity._attr_hvac_action = None

    await entity.async_turn_on()
    coordinator.comm.send_message.assert_awaited_once_with(
        destination=5,
        command=4,
        data1=0,
        data2=3,
        cb=entity._process_response_message,
    )

    # Simulate receiving NACK response (no Entity changes expected)
    entity._process_response_message({"command": 2, "data1": 0, "data2": 0x03})
    # Internal state is still stored
    assert entity._attr_available is False
    assert entity._attr_hvac_action == None
    entity.async_write_ha_state.assert_not_called()

    # Simulate receiving ACK response (Entity should update state to available and HVACAction.OFF)
    entity._process_response_message({"command": 1, "data1": 0, "data2": 0x03})
    assert entity._attr_available is True
    assert entity._attr_hvac_action == None
    entity.async_write_ha_state.assert_called_once()

    # Reset and test async_turn_off
    coordinator.comm.send_message.reset_mock()

    await entity.async_turn_off()
    coordinator.comm.send_message.assert_awaited_once_with(
        destination=5,
        command=4,
        data1=0,
        data2=2,
        cb=entity._process_response_message,
    )

    # Simulate receiving ACK message
    entity._process_response_message({"command": 1, "data1": 0, "data2": 2})

    assert entity._attr_available == True
    assert entity._attr_hvac_action == HVACAction.OFF


@pytest.mark.asyncio
async def test_ingenium_climate_mode_controls(hass, device_1, features, coordinator):
    """Test mode control send payloads and response handling for ACK/NACK messages."""
    entry = MockConfigEntry(
        domain="ingenium",
        data={"mac": "A123B", "host": "192.168.1.100"},
    )
    entry.add_to_hass(hass)
    entry.runtime_configuration = {
        "coordinator": coordinator,
        "devices": [],
    }

    entity = ingenium_climate.IngeniumClimate(entry, device_1, features)
    entity.async_write_ha_state = MagicMock()
    entity._attr_fan_mode = FAN_AUTO
    entity._attr_hvac_action = HVACAction.OFF

    await entity.async_set_hvac_mode(HVACMode.COOL)
    assert coordinator.comm.send_message.await_count == 2
    # The first message sets uses existing fan mode to AUTO (0x40) and HVAC mode to COOL (0x0)
    coordinator.comm.send_message.assert_any_await(
        destination=5,
        command=4,
        data1=1,
        data2=0x40,
        cb=entity._process_response_message,
    )
    # Second message turns on the AC unit (data2=3)
    coordinator.comm.send_message.assert_any_await(
        destination=5,
        command=4,
        data1=0,
        data2=3,
        cb=entity._process_response_message,
    )

    # Simulate receiving NACK response
    entity._process_response_message({"command": 2, "data1": 1, "data2": 0x40})
    # Internal state is still stored
    assert entity._attr_fan_mode == FAN_AUTO
    assert entity._attr_hvac_mode == None
    entity.async_write_ha_state.assert_not_called()

    coordinator.comm.send_message.reset_mock()
    entity.async_write_ha_state.reset_mock()

    # Simulate receiving ACK response
    entity._process_response_message({"command": 1, "data1": 1, "data2": 0x40})
    assert entity._attr_fan_mode == FAN_AUTO
    assert entity._attr_hvac_mode == HVACMode.COOL
    entity.async_write_ha_state.assert_called_once()
