import asyncio
import logging

from struct import pack, unpack
from typing import List, Callable

_LOGGER = logging.getLogger(__name__)


class IngeniumBUSingCommunication:
    """Class to Communicate over BUSing protocol with Ingenium server."""

    DEFAULT_PORT = 12347
    RESPONSE_TIMEOUT = 15
    RECONNECT_DELAY = 5
    RECONNECT_RETRIES = 5
    BUFFER_DELAY = 0.2
    DEFAULT_POLLING_INTERVAL = 300

    def __init__(
        self, host: str, port: int = DEFAULT_PORT, retries: int = RECONNECT_RETRIES
    ):
        self._host = host
        self._port = port
        self._retries = retries
        self._reader = None
        self._writer = None
        self._msg_buffer = []
        self._future_messages = False

    async def listener(
        self,
        callback=None,
        buffer_flush_delay: None | float = BUFFER_DELAY,
        polling_interval: None | int = None,
    ):
        """TCP client task that connects to device and logs incoming data in hex."""
        flush_task = polling_task = None

        while True:
            try:
                if polling_interval is not None and polling_interval > 0:
                    # Schedule polling messages at the configured interval
                    if polling_task is None or polling_task.done():
                        polling_task = asyncio.create_task(
                            self._polling_periodically(polling_interval)
                        )

                while True:
                    [
                        self._msg_buffer.append(msg)
                        for msg in await self._read_messages()
                    ]

                    # Schedule (always) 1 task for flushing the message buffer
                    if flush_task is None or flush_task.done():
                        flush_task = asyncio.create_task(
                            self._flush_buffer(callback, buffer_flush_delay)
                        )

            except IOError as e:
                _LOGGER.warning("IOError occurred: %s", e)
                continue

            except asyncio.CancelledError:
                _LOGGER.info("Listener cancelled, closed connection")
                break

    async def send_message(
        self,
        command: int,
        destination: int,
        data1: int,
        data2: int,
        _origin: int = None,
        cb: None | Callable = None,
    ) -> bool:
        """Send structured Ingenium BUSing message."""
        origin = 0xFFFF  # Start bytes
        message = IngeniumBUSingDatagram.encode(
            origin, command, destination, data1, data2
        )

        res = await self.send_message_raw(message)

        if cb:
            cb(await self.await_response())

        return res

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
        while timeout > 0:
            start_t = asyncio.get_event_loop().time()

            _LOGGER.debug(f"Waiting for response message (timeout={timeout})...")

            try:
                d = await asyncio.wait_for(self._read_messages(), timeout=timeout)

                for msg in d:
                    if msg["command"] == 1 or msg["command"] == 2:
                        return msg
            except Exception as e:
                _LOGGER.warning(f"Failed to read messages: {e}")
            finally:
                # Shorten the timeout for the next loop iteration to account for time already spent waiting
                timeout -= asyncio.get_event_loop().time() - start_t

    async def poll_bus_devices(self):
        await self.send_message(destination=0xFFFF, command=10, data1=0, data2=0)

    async def _polling_periodically(self, polling_interval):
        while True:
            await asyncio.sleep(polling_interval)
            await self.poll_bus_devices()

    async def _open_connection(self):
        if (
            self._reader is not None
            and self._writer is not None
            and not self._writer.is_closing()
        ):
            return

        if self._writer is not None:
            await self._close_connection()

        # Connection is alive - reset retries
        retries = 1

        while True:
            try:
                self._reader, self._writer = await asyncio.open_connection(
                    self._host, self._port
                )
                _LOGGER.info("Connected to %s:%d", self._host, self._port)
                break

            except (IOError, ConnectionRefusedError) as e:
                _LOGGER.warning(
                    f"{e}, attempt {retries}/{self._retries}, retrying in {self.RECONNECT_DELAY} seconds"
                )
                retries += 1

                if retries > self._retries:
                    raise e

                await asyncio.sleep(self.RECONNECT_DELAY)

    async def _close_connection(self):
        if not self._writer.is_closing():
            self._writer.close()

        await self._writer.wait_closed()

        self._reader = self._writer = None

    async def _read_messages(self):
        try:
            if not self._future_messages or self._future_messages.done():
                self._future_messages = asyncio.create_task(self._await_messages())

            res = await self._future_messages
        finally:
            self._future_messages = False

        return res

    async def _await_messages(self):
        await self._open_connection()

        # Read up to 100 datagrams at the time
        MAX_READ = 9 * 100

        data = await self._reader.read(MAX_READ)

        if not data:
            if self._reader.at_eof():
                self._reader = None
            raise IOError("Lost connection")

        decoded_messages = IngeniumBUSingDatagram.decode(data)

        [_LOGGER.debug(f"Decoded message: {msg}") for msg in decoded_messages]

        return decoded_messages

    async def _flush_buffer(self, cb, delay: None | float):
        """Async flush message buffer content to callback"""
        if not delay is None and delay > 0:
            # Delay a little longer for more messages to arrive
            await asyncio.sleep(delay)

        msgs = self._msg_buffer
        if len(msgs) > 0:
            _LOGGER.debug(f"Flushing {len(msgs)} message(s) from buffer")
            self._msg_buffer = []
            # Trigger callback with message buffer contents
            if not cb is None:
                cb(msgs)


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
            cmd, destination, origin, data1, data2 = unpack(">xxbHHBB", dg)
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
