"""Basic tests for the Ingenium integration."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from custom_components.ingenium import (
    async_setup_entry,
    async_unload_entry,
    async_reload_entry,
)

from pytest_homeassistant_custom_component.common import MockConfigEntry


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
        assert isinstance(entry.runtime_configuration["coordinator"], Device)
        assert isinstance(entry.runtime_configuration["devices"], list)
        mock_forward.assert_called_once()


@pytest.mark.asyncio
async def test_unload(hass):
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
        patch.object(
            hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
        ) as mock_unload,
    ):
        await async_setup_entry(hass, entry)

        coordinator = entry.runtime_configuration["coordinator"]
        coordinator._listener = Mock(cancel=Mock())

        await async_unload_entry(hass, entry)

        assert mock_forward.call_count == 1
        assert mock_unload.call_count == 1
        coordinator._listener.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_reload(hass):
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
        patch.object(
            hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
        ) as mock_unload,
    ):
        await async_setup_entry(hass, entry)

        coordinator = entry.runtime_configuration["coordinator"]
        coordinator._listener = Mock(cancel=Mock())

        await async_reload_entry(hass, entry)

        assert mock_forward.call_count == 2
        assert mock_unload.call_count == 1
        coordinator._listener.cancel.assert_called_once()
