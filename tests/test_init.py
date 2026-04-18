"""Basic tests for the Ingenium integration."""

from unittest.mock import patch, AsyncMock

from custom_components.ingenium import async_setup_entry

from pytest_homeassistant_custom_component.common import MockConfigEntry


# @pytest.mark.asyncio
async def test_setup_entry(hass):
    entry = MockConfigEntry(
        domain="ingenium", data={"mac": "A123B", "host": "192.168.1.100"}
    )
    entry.add_to_hass(hass)

    # Import the Device class
    from custom_components.ingenium.device import Device

    with (
        patch.object(Device, "async_initialize_device", return_value=True),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ) as mock_forward,
    ):
        result = await async_setup_entry(hass, entry)

        assert result is True
        mock_forward.assert_called_once()
