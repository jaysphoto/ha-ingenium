"""Basic tests for the Ingenium integration."""
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_setup_entry(hass):
    entry = MockConfigEntry(domain="ingenium", data={})
    entry.add_to_hass(hass)

    # Import the integration and call async_setup_entry
    from custom_components.ingenium import async_setup_entry

    assert await async_setup_entry(hass, entry)
