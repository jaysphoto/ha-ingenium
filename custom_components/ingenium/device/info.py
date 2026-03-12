class IngeniumDeviceInfo:
    """Base class for detected ingenium device information."""

    def __init__(self, serial: str, credential: str):
        """Initialize the device."""
        self._serial = serial
        self._credential = credential

    @property
    def serial(self) -> str:
        """Return the serial number of the device."""
        return self._serial
