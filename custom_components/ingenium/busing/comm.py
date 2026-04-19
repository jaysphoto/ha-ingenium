import asyncio
import logging

from struct import pack, unpack
from typing import List

_LOGGER = logging.getLogger(__name__)


class IngeniumBUSingCommunication:
    """Class to Communicate over BUSing protocol with Ingenium server."""

    DEFAULT_PORT = 12347
    RESPONSE_TIMEOUT = 15
    RECONNECT_DELAY = 5
    RECONNECT_RETRIES = 5

    def __init__(
        self, host: str, port: int = DEFAULT_PORT, retries: int = RECONNECT_RETRIES
    ):
        self._host = host
        self._port = port
        self._reader = None
        self._writer = None
        self._retries = retries

    async def listener(self, callback=None):
        retries = self._retries
        """TCP client task that connects to device and logs incoming data in hex."""
        while True:
            try:
                await self._open_connection()

                try:
                    while True:
                        d = await self._read_messages()

                        if d is None:
                            raise IOError("Lost connection")

                        # Connection is alive - reset retries
                        retries = self._retries
                        if not callback is None:
                            callback(d)
                finally:
                    await self._close_connection()
            except asyncio.CancelledError:
                _LOGGER.info("Listener cancelled, closed connection")
                break
            except IOError as e:
                if retries == 0:
                    _LOGGER.warning(
                        f"Connection failed: {e}, giving up after {self._retries} tries"
                    )
                    break

                _LOGGER.warning(
                    f"Connection failed: {e}, retrying in {self.RECONNECT_DELAY} seconds"
                )
                retries = retries - 1
                await asyncio.sleep(self.RECONNECT_DELAY)

    async def send_message(
        self, command: int, _origin: int, destination: int, data1: int, data2: int
    ):
        """Send structured Ingenium BUSing message."""
        origin = 0xFFFF  # Start bytes
        message = IngeniumBUSingDatagram.encode(
            origin, command, destination, data1, data2
        )

        return await self.send_message_raw(message)

    async def send_message_raw(self, message: bytearray | bytes):
        """Send raw Ingenium BUSing message."""
        await self._open_connection()

        try:
            _LOGGER.info("Sending raw message: %s", message.hex())
            self._writer.write(message)
            return await self._writer.drain()
        except Exception as e:
            _LOGGER.error("Failed to send message: %s", e)

    async def await_response(self, timeout=RESPONSE_TIMEOUT) -> dict | None:
        """Wait for a matching response, RequestReply pattern implementation."""
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
        if self._reader is None:
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
        # Read up to 100 datagrams at the time
        data = await self._reader.read(9 * 100)
        if not data:
            return None

        decoded_messages = IngeniumBUSingDatagram.decode(data)

        [_LOGGER.debug("Received datagram: %s", msg) for msg in decoded_messages]

        return decoded_messages


class IngeniumBUSingDatagram:
    def decode(data: bytes) -> List[dict]:
        """
        Decode recieved bytes into a list of structured dictionary.

        Messages on the bus are sent in 9-byte frames, for example:

        Connected to 192.168.xxx.xx:12347
        Received data: fefe04000bfefe2300
        Received data: fefe04000b000b0002
        Received data: fefe04000b000b0113fefe04000b000b0208fefe04000b000b0370
        """
        messages = []
        offset = 0
        while offset < len(data):
            # Datagrams are each 9 bytes long, so we read in chunks of 9 bytes
            dg = data[offset : offset + 9]
            if len(dg) < 9:
                raise IngeniumBUSingDataInvalid(
                    f"Incomplete datagram received: {dg.hex()}"
                )
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

    def encode(origin, command, destination, data1, data2) -> bytearray:
        # Construct the message according to the protocol
        return pack(">HHbbb", origin, destination, command, data1, data2)


class IngeniumBUSingDataInvalid(IOError):
    pass
