import asyncio
import logging

from struct import unpack
from typing import List

_LOGGER = logging.getLogger(__name__)


class IngeniumBUSingCommunication:
    """Class to Communicate over BUSing protocol with Ingenium server."""

    DEFAULT_PORT = 12347

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        decoder: "IngeniumBUSingDecoder" = None,
    ):
        self._host = host
        self._port = port
        self._decoder = decoder or IngeniumBUSingDecoder()

    async def listener(self):
        """TCP client task that connects to device and logs incoming data in hex."""
        while True:
            try:
                self._reader, self._writer = await asyncio.open_connection(
                    self._host, self._port
                )
                _LOGGER.info("Connected to %s:%d", self._host, self._port)
                try:
                    while True:
                        data = await self._reader.read(1024)
                        if not data:
                            break

                        decoded_messages = self._decoder.decode_message(data)

                        # TODO: instead of logging, we should dispatch these messages to the rest of the library
                        [
                            _LOGGER.debug("Received datagram: %s", msg)
                            for msg in decoded_messages
                        ]
                finally:
                    self._writer.close()
                    await self._writer.wait_closed()
            except asyncio.CancelledError:
                _LOGGER.info("Listener cancelled, closed connection")
                break
            except Exception as e:
                _LOGGER.error("Connection failed: %s, retrying in 5 seconds", e)
                await asyncio.sleep(5)

    async def send_message(
        self, command: int, origin: int, destination: int, data1: int, data2: int
    ):
        """Send a message to the Ingenium server."""
        if not hasattr(self, "_writer") or self._writer is None:
            _LOGGER.error("Not connected to server, cannot send message")
            return

        # Construct the message according to the protocol
        message = bytearray(7)
        message[0] = 0xFE  # Start byte
        message[1] = 0xFE  # Start byte
        message[2] = command & 0xFF
        message[3] = (destination >> 8) & 0xFF
        message[4] = (destination) & 0xFF
        message[5] = data1 & 0xFF
        message[6] = data2 & 0xFF

        try:
            _LOGGER.info("Sending: %s", message.hex())
            self._writer.write(message)
            await self._writer.drain()
        except Exception as e:
            _LOGGER.error("Failed to send message: %s", e)


class IngeniumBUSingDecoder:
    """
    Class to decode BUSing protocol messages from Ingenium server.
    Messages on the bus are sent in 9-byte frames, for example:
    Connected to 192.168.xxx.xx:12347
    Received data: fefe04000bfefe2300
    Received data: fefe04000b000b0002
    Received data: fefe04000b000b0113fefe04000b000b0208fefe04000b000b0370
    """

    def decode_message(self, data: bytes) -> List[dict]:
        """Decode recieved bytes into a list of structured dictionary."""
        messages = []
        offset = 0
        while offset < len(data):
            # Datagrams are each 9 bytes long, so we read in chunks of 9 bytes
            dg = data[offset : offset + 9]
            if len(dg) < 9:
                _LOGGER.warning("Incomplete datagram received: %s", dg.hex())
                break
            cmd, origin, destination, data1, data2 = unpack(">xxbHHBB", dg)
            decoded = {
                "raw": dg.hex(),
                "command": cmd,
                "origin": origin,
                "destination": destination,
                "data1": data1,
                "data2": data2,
            }
            messages.append(decoded)
            # Move to the next message (assuming 9 bytes per message)
            offset += 9

        return messages
