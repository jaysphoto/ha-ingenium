"""Config flow tests for the Ingenium integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.ingenium import config_flow
from custom_components.ingenium.const import (
    CONF_HOST,
    CONF_IGNORE_AVAILABILITY,
    CONF_INSTALLATION_DATA,
    CONF_MAC,
    CONF_VERSION,
)
from custom_components.ingenium.http import IngeniumHttpInstallEntry


@pytest.mark.asyncio
async def test_config_flow_successful_setup(hass):
    """Test successful config flow setup with mocked HTTP responses."""
    # Mock the HTTP client and its methods
    mock_http = MagicMock()
    mock_http.is_v3 = AsyncMock(return_value=False)
    # Mock the config property

    async def _mock_config():
        return {"MAC": "AA:BB:CC:DD:EE:FF"}

    mock_http.config = _mock_config()
    mock_installation_data = [
        IngeniumHttpInstallEntry(label="Device 1", type=1, output=1, address=1),
        IngeniumHttpInstallEntry(label="Device 2", type=2, output=2, address=2),
    ]
    mock_http.installation_data = AsyncMock(return_value=mock_installation_data)

    # Patch the get_device_http method to return our mock
    with patch.object(
        config_flow.IngeniumConfigFlow, "get_device_http", return_value=mock_http
    ):
        # Initialize the config flow
        flow = config_flow.IngeniumConfigFlow()
        flow.hass = hass

        # Step 1: User provides host
        result = await flow.async_step_user({CONF_HOST: "192.168.1.100"})

        # Should proceed to devices step
        assert result["type"] == "form"
        assert result["step_id"] == "devices"

        # Step 2: User selects to ignore availability
        result = await flow.async_step_devices({CONF_IGNORE_AVAILABILITY: []})

        # Should create the entry
        assert result["type"] == "create_entry"
        assert result["title"] == "Ingenium at 192.168.1.100"
        assert result["data"][CONF_VERSION] == 1
        assert result["data"][CONF_MAC] == "AA:BB:CC:DD:EE:FF"
        assert (
            result["data"]["device"][CONF_INSTALLATION_DATA] == mock_installation_data
        )
