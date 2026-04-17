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
from custom_components.ingenium.device import IgnoredBUSDevice
from custom_components.ingenium.http import IngeniumHttpInstallEntry


@pytest.mark.asyncio
async def test_config_flow_simple_setup(hass):
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

        # Step 2: User selects to ignore availability (using section-based format)
        result = await flow.async_step_devices(
            {
                f"{CONF_IGNORE_AVAILABILITY}_type_1": {CONF_IGNORE_AVAILABILITY: []},
                f"{CONF_IGNORE_AVAILABILITY}_type_2": {CONF_IGNORE_AVAILABILITY: []},
            }
        )

        # Should create the entry
        assert result["type"] == "create_entry"
        assert result["title"] == "Ingenium at 192.168.1.100"
        assert result["data"][CONF_VERSION] == 1
        assert result["data"][CONF_MAC] == "AA:BB:CC:DD:EE:FF"
        assert result["data"][CONF_IGNORE_AVAILABILITY] == []
        assert (
            result["data"]["device"][CONF_INSTALLATION_DATA] == mock_installation_data
        )


@pytest.mark.asyncio
async def test_config_flow_ignore_device_setup(hass):
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

        # Step 2: User selects to ignore availability (using section-based format)
        result = await flow.async_step_devices(
            {
                f"{CONF_IGNORE_AVAILABILITY}_type_1": {
                    CONF_IGNORE_AVAILABILITY: ["1-1"]
                },
                f"{CONF_IGNORE_AVAILABILITY}_type_2": {CONF_IGNORE_AVAILABILITY: []},
            }
        )

        # Should create the entry
        assert result["type"] == "create_entry"
        assert result["title"] == "Ingenium at 192.168.1.100"
        assert result["data"][CONF_VERSION] == 1
        assert result["data"][CONF_MAC] == "AA:BB:CC:DD:EE:FF"
        assert result["data"][CONF_IGNORE_AVAILABILITY] == [
            IgnoredBUSDevice(address="1", type="1", output="1")
        ]
        assert (
            result["data"]["device"][CONF_INSTALLATION_DATA] == mock_installation_data
        )


@pytest.mark.asyncio
async def test_config_flow_list_devices_with_ignore_selection(hass):
    """Test that step 2 shows a form with the bus devices and allows for ignoring their availability."""
    # Mock the HTTP client and its methods
    mock_http = MagicMock()
    mock_http.is_v3 = AsyncMock(return_value=False)

    async def _mock_config():
        return {"MAC": "AA:BB:CC:DD:EE:FF"}

    mock_http.config = _mock_config()

    # Create mock installation data with different types and addresses
    mock_installation_data = [
        IngeniumHttpInstallEntry(label="Climate Device", type=47, output=0, address=11),
        IngeniumHttpInstallEntry(
            label="Scene: Intrusion Alarm Off", type=26, output=0, address=1
        ),
        IngeniumHttpInstallEntry(
            label="Scene: Intrusion Alarm On", type=26, output=0, address=4
        ),
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

        # Step 2: Verify the form structure
        assert result["type"] == "form"
        assert result["step_id"] == "devices"

        # Verify the data schema contains one section per device type.
        data_schema = result["data_schema"]
        schema_dict = data_schema.schema

        section_keys = {
            key.schema: schema_dict[key]
            for key in schema_dict
            if hasattr(key, "schema")
            and isinstance(key.schema, str)
            and key.schema.startswith(f"{CONF_IGNORE_AVAILABILITY}_type_")
        }

        assert len(section_keys) == 2, (
            f"Expected 2 device type sections, got {list(section_keys)}"
        )

        expected_section_map = {
            f"{CONF_IGNORE_AVAILABILITY}_type_47": [
                {"value": "11-0", "label": "Climate Device"}
            ],
            f"{CONF_IGNORE_AVAILABILITY}_type_26": [
                {"value": "1-0", "label": "Scene: Intrusion Alarm Off"},
                {"value": "4-0", "label": "Scene: Intrusion Alarm On"},
            ],
        }

        for section_name, expected_options in expected_section_map.items():
            assert section_name in section_keys, f"Missing section {section_name}"
            section = section_keys[section_name]
            assert hasattr(section, "schema"), (
                "Section value should expose a nested schema"
            )

            nested_schema = section.schema.schema
            nested_key = None
            for key in nested_schema:
                if hasattr(key, "schema") and key.schema == CONF_IGNORE_AVAILABILITY:
                    nested_key = key
                    break

            assert nested_key is not None, (
                f"Missing {CONF_IGNORE_AVAILABILITY} field inside section {section_name}"
            )

            selector_config = nested_schema[nested_key]
            if hasattr(selector_config, "config"):
                selector_dict = selector_config.config
            elif isinstance(selector_config, dict):
                selector_dict = selector_config.get("select", {})
            else:
                selector_dict = (
                    vars(selector_config)
                    if hasattr(selector_config, "__dict__")
                    else {}
                )

            options = selector_dict.get("options", [])
            assert options == expected_options, (
                f"Expected options {expected_options} for {section_name}, got {options}"
            )
