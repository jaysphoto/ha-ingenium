import asyncio
import logging

from struct import unpack
from typing import List

_LOGGER = logging.getLogger(__name__)


class IngeniumBUSingCommunication:
    """Class to Communicate over BUSing protocol with Ingenium server."""

    DEFAULT_PORT = 12347
    RESPONSE_TIMEOUT = 15
    RECONNECT_DELAY = 5

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        decoder: "IngeniumBUSingDecoder" = None,
    ):
        self._host = host
        self._port = port
        self._decoder = decoder or IngeniumBUSingDecoder()

    async def listener(self, callback=None):
        """TCP client task that connects to device and logs incoming data in hex."""
        while True:
            try:
                await self._open_connection()

                try:
                    while True:
                        d = await self._read_messages()

                        if d is None:
                            break

                        if callback is not None:
                            callback(d)
                finally:
                    await self._close_connection()
            except asyncio.CancelledError:
                _LOGGER.info("Listener cancelled, closed connection")
                break
            except Exception as e:
                _LOGGER.error(
                    f"Connection failed: {e}, retrying in {self.RECONNECT_DELAY} seconds"
                )
                await asyncio.sleep(self.RECONNECT_DELAY)

    async def send_message(
        self, command: int, origin: int, destination: int, data1: int, data2: int
    ):
        """Send a message to the Ingenium server."""
        if not hasattr(self, "_writer") or self._writer is None:
            _LOGGER.error("Not connected to server, cannot send message")
            return

        # Construct the message according to the protocol
        message = bytearray(7)
        message[0] = b"\xff"  # Start byte
        message[1] = b"\xff"  # Start byte
        message[2] = command & 0xFF
        message[3] = (destination >> 8) & 0xFF
        message[4] = (destination) & 0xFF
        message[5] = data1 & 0xFF
        message[6] = data2 & 0xFF

        return await self.send_message_raw(message)

    async def send_message_raw(self, message: bytearray | bytes):
        await self._open_connection()
        try:
            _LOGGER.info("Sending: %s", message.hex())
            self._writer.write(message)
            return await self._writer.drain()
        except Exception as e:
            _LOGGER.error("Failed to send message: %s", e)

    async def await_response(self, timeout=RESPONSE_TIMEOUT) -> dict | None:
        start_t = asyncio.get_event_loop().time()
        while timeout > 0:
            _LOGGER.debug(f"Waiting for response message (timeout={timeout})...")
            d = await asyncio.wait_for(self._read_messages(), timeout=timeout)

            if d is None:
                break

            for msg in d:
                if msg["command"] == 1 or msg["command"] == 2:
                    return msg
            # Shorten the timeout for the next loop iteration to account for time already spent waiting
            timeout = timeout - (asyncio.get_event_loop().time() - start_t)

    async def _open_connection(self):
        if not hasattr(self, "_reader") or self._reader is None:
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )
        _LOGGER.info("Connected to %s:%d", self._host, self._port)

    async def _close_connection(self):
        if not self._writer.is_closing():
            self._writer.close()
            await self._writer.wait_closed()

        self._reader = self._writer = None

    async def _read_messages(self) -> List[dict] | None:
        if self._reader.at_eof():
            return None

        data = await self._reader.read(1024)
        if not data:
            return None

        decoded_messages = self._decoder.decode_message(data)

        [_LOGGER.debug("Received datagram: %s", msg) for msg in decoded_messages]

        return decoded_messages


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
