"""Config flow tests for the Ingenium integration."""

import pytest
from unittest.mock import MagicMock, patch

from custom_components.ingenium import config_flow
from custom_components.ingenium.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_IGNORE_AVAILABILITY,
    CONF_INSTALLATION_DATA,
    CONF_MAC,
    CONF_VERSION,
)


@pytest.fixture
async def mock_http(mock_installation_data):
    """Mock HTTP API responses"""

    async def is_v3():
        return False

    async def config():
        return {"MAC": "AA:BB:CC:DD:EE:FF"}

    async def installation_data():
        return mock_installation_data

    mock_http = MagicMock()
    mock_http.is_v3 = is_v3()
    mock_http.config = config()
    mock_http.installation_data = installation_data()
    return mock_http


@pytest.fixture
def mock_installation_data():
    return [
        {"label": "AC GENERAL", "type": 47, "output": 0, "address": 11},
        {"label": "INTRUSION ON", "type": 26, "output": 0, "address": 4},
        {"label": "INTRUSION OFF", "type": 26, "output": 0, "address": 5},
    ]


@pytest.mark.asyncio
async def test_config_flow_simple_setup(hass, mock_http, mock_installation_data):
    """Test successful config flow setup with mocked HTTP responses."""

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
        assert isinstance(result["data"], dict)
        assert result["data"][CONF_VERSION] == 1
        assert result["data"][CONF_MAC] == "AA:BB:CC:DD:EE:FF"
        assert result["data"][CONF_IGNORE_AVAILABILITY] == []
        assert result["data"][CONF_DEVICE] == {
            CONF_INSTALLATION_DATA: mock_installation_data
        }


@pytest.mark.asyncio
async def test_config_flow_list_devices_with_ignore_selection(hass, mock_http):
    """Test that step 2 shows a form with the bus devices and allows for ignoring their availability."""

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
                {"value": "11-0", "label": "AC GENERAL"}
            ],
            f"{CONF_IGNORE_AVAILABILITY}_type_26": [
                {"value": "4-0", "label": "INTRUSION ON"},
                {"value": "5-0", "label": "INTRUSION OFF"},
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
