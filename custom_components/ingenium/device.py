"""Ingenium touch device coordinator"""

from homeassistant import core

from .const import CONF_HOST


class IngeniumDevice:
    """Class to represent a Ingenium touch device."""

    def __init__(self, hass: core.HomeAssistant, config_entry: dict):
        self.config_entry = config_entry
        self.hass = hass

    @property
    def host(self) -> str:
        """Return the host of the ingenium touch device."""
        return self.config_entry.data[CONF_HOST]
