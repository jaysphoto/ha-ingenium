import asyncio
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class IngeniumBUSingCommunication:
    """Class to Communicate over BUSing protocol with Ingenium server."""

    def __init__(self, host: str, port: int = 12347):
        self._host = host
        self._port = port

    async def listener(self):
        """TCP client task that connects to device and logs incoming data in hex."""
        while True:
            try:
                reader, writer = await asyncio.open_connection(self._host, self._port)
                _LOGGER.info("Connected to %s:%d", self._host, self._port)
                try:
                    while True:
                        data = await reader.read(1024)
                        if not data:
                            break
                        hex_data = data.hex()
                        _LOGGER.info("Received data: %s", hex_data)
                finally:
                    writer.close()
                    await writer.wait_closed()
            except asyncio.CancelledError:
                _LOGGER.info("Listener cancelled, closed connection")
                break
            except Exception as e:
                _LOGGER.error(
                    "Connection failed: %s, retrying in 5 seconds", e)
                await asyncio.sleep(5)
