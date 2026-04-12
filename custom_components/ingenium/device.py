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


class IngeniumDeviceInfo:
    """
    Base class for detected ingenium device information.

    Format comes from /Instal.dat, has multi-line entries for each device:

        LINE 0: map     (integer) or "KNX" FOR KNX DEVICES, otherwise the "page number" on the display
        LINE 1: label   (UTF-8 string OR EMPTY, KNX devices handle this field differently!)
        LINE 2: posX    (integer)
        LINE 3: posY    (integer)
        LINE 4: address (interger) or real1 (float)
        LINE 5: output  (integer)
        LINE 6: type    (integer)
        LINE 7: icon    (integer), KNX devices handle this field differently!

    """

    def __init__(self, label: str, type: int, address: int):
        """Initialize the device."""
        self._label = label
        self._type = type
        self._address = address

    @property
    def label(self) -> str:
        """Return the label of the device."""
        return self._label

    @property
    def type(self) -> int:
        """Return the type of the device."""
        return self._type

    @property
    def address(self) -> int:
        """Return the address of the device."""
        return self._address
