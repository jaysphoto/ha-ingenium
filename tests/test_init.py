"""Basic tests for the Ingenium integration."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from custom_components.ingenium import (
    async_setup_entry,
    async_unload_entry,
    async_reload_entry,
    async_remove_config_entry_device,
)

from custom_components.ingenium.const import (
    DOMAIN,
    CONF_MAC,
    CONF_HOST,
)
from custom_components.ingenium.device import Device

from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_setup_entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_MAC: "A123B", CONF_HOST: "192.168.1.100"}
    )
    entry.add_to_hass(hass)

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
        domain=DOMAIN, data={CONF_MAC: "A123B", CONF_HOST: "192.168.1.100"}
    )
    entry.add_to_hass(hass)

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
        domain=DOMAIN, data={CONF_MAC: "A123B", CONF_HOST: "192.168.1.100"}
    )
    entry.add_to_hass(hass)

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


@pytest.mark.asyncio
async def test_remove_config_entry_device(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_MAC: "A123B", CONF_HOST: "192.168.1.100"}
    )
    entry.add_to_hass(hass)

    with (
        patch.object(Device, "async_initialize_device", return_value=True),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ),
    ):
        await async_setup_entry(hass, entry)

        assert (
            await async_remove_config_entry_device(
                hass, entry, Mock(identifiers=[("ingenium", "A123B")])
            )
            is False
        )
        assert (
            await async_remove_config_entry_device(
                hass, entry, Mock(identifiers=[("ingenium", "A123B", 1, 1)])
            )
            is True
        )


@pytest.mark.asyncio
async def test_remove_config_entry_known_device(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_MAC: "A123B", CONF_HOST: "192.168.1.100"}
    )
    entry.add_to_hass(hass)

    from custom_components.ingenium.device import BUSDevice, BusDeviceType

    with (
        patch.object(Device, "async_initialize_device", return_value=True),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ),
        patch.object(
            Device,
            "get_devices",
            return_value=[BUSDevice(1, "GENERAL", BusDeviceType, 47, 1)],
        ),
    ):
        await async_setup_entry(hass, entry)

        assert (
            await async_remove_config_entry_device(
                hass, entry, Mock(identifiers=[("ingenium", "A123B", 1)])
            )
            is True
        )
        assert (
            await async_remove_config_entry_device(
                hass, entry, Mock(identifiers=[("ingenium", "A123B", 1, 40)])
            )
            is True
        )
        assert (
            await async_remove_config_entry_device(
                hass, entry, Mock(identifiers=[("ingenium", "A123B", 1, 47)])
            )
            is False
        )
        assert (
            await async_remove_config_entry_device(
                hass, entry, Mock(identifiers=[("ingenium", "A123B", 2, 47)])
            )
            is True
        )
