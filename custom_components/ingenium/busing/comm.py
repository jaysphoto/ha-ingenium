import asyncio
import logging

from struct import pack, unpack
from typing import List, Callable

_LOGGER = logging.getLogger(__name__)


class IngeniumBUSingCommunication:
    """Class to Communicate over BUSing protocol with Ingenium server."""

    DEFAULT_PORT = 12347
    RESPONSE_TIMEOUT = 15
    RECONNECT_RETRIES = 5
    RECONNECT_DELAY = 5
    BUFFER_DELAY = 0.2
    DEFAULT_POLLING_INTERVAL = 180

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        connect_retries: int = RECONNECT_RETRIES,
        reconnect_delay: int = RECONNECT_DELAY,
        response_timeout: int = RESPONSE_TIMEOUT,
    ):
        self._host = host
        self._port = port
        self._reader = None
        self._writer = None
        self._retries = connect_retries
        self._reconnect_delay = reconnect_delay
        self._response_timeout = response_timeout
        self._msg_buffer = []
        self._future_messages = False
        # asyncio Lock/Task used to allow multiple coroutines to await the same Stream reader
        self._reader_lock = asyncio.Lock()
        self._reader_task: asyncio.Task | None = None

    def set_response_timeout(self, timeout: int | None) -> None:
        """Change response timeout value for the next awaited response"""
        self._response_timeout = timeout

    async def listener(
        self,
        callback: Callable,
        buffer_flush_delay: None | float = BUFFER_DELAY,
        auto_reconnect: bool = True,
    ):
        """TCP client task that connects to device and logs incoming data in hex."""
        flush_task = None

        while True:
            try:
                while True:
                    [
                        self._msg_buffer.append(msg)
                        for msg in await self._await_messages()
                    ]

                    # Schedule (always) 1 task for flushing the message buffer
                    if flush_task is None or flush_task.done():
                        flush_task = asyncio.create_task(
                            self._flush_buffer(callback, buffer_flush_delay)
                        )

            except IOError as e:
                if auto_reconnect:
                    _LOGGER.warning(
                        "IOError in listener: %s, reconnecting in %d seconds",
                        e,
                        self._reconnect_delay,
                    )
                    await asyncio.sleep(self._reconnect_delay)
                else:
                    raise

            except asyncio.CancelledError:
                _LOGGER.info("Listener cancelled, closing connection")
                break

    async def send_message(
        self,
        command: int,
        destination: int,
        data1: int,
        data2: int,
        _origin: int = None,
        cb: None | Callable = None,
    ) -> None:
        """Send structured Ingenium BUSing message."""
        origin = 0xFFFF  # Start bytes
        message = IngeniumBUSingDatagram.encode(
            origin, command, destination, data1, data2
        )

        await self.send_message_raw(message)

        # (optional) Create response callback co-routine, waiting for reply with matching origin
        if not cb is None:
            asyncio.create_task(
                self._do_callback(cb, await self.await_response(origin=destination))
            )

    async def send_message_raw(self, message: bytearray | bytes) -> None:
        """Send raw Ingenium BUSing message."""
        await self._open_connection()

        _LOGGER.debug("Sending raw message: %s", message.hex())

        self._writer.write(message)
        await self._writer.drain()

    async def await_response(self, origin: int | None = None) -> dict | None:
        """Wait for a matching response, up until the value of response_timeout (in seconds)."""
        timeout = self._response_timeout

        start_t = asyncio.get_event_loop().time()

        while True:
            _LOGGER.debug("Waiting for response message (timeout=%i)...", timeout)

            try:
                for msg in await self._await_messages(timeout=timeout):
                    if msg["command"] == 1 or msg["command"] == 2:
                        # Apply message origin filter (optional)
                        if origin == None or (msg["origin"] == origin & 0xFF):
                            _LOGGER.debug("Matched Response Message: %s", msg)
                            return msg
            except IOError as e:
                _LOGGER.warning("IOError occurred: %s", e)

            finally:
                if self._response_timeout is not None:
                    # Check the time already spent waiting, break if timed out
                    timeout = self._response_timeout - (
                        asyncio.get_event_loop().time() - start_t
                    )
                    if timeout <= 0:
                        raise asyncio.TimeoutError

    async def poll_bus_devices(self):
        await self.send_message(destination=0xFFFF, command=10, data1=0, data2=0)

    async def _open_connection(self):
        if (
            self._reader is not None
            and not self._reader.at_eof()
            and self._writer is not None
            and not self._writer.is_closing()
        ):
            return

        # Starting new connection - reset retries
        retries = 1

        while True:
            try:
                self._reader, self._writer = await asyncio.open_connection(
                    self._host, self._port
                )
                _LOGGER.info("Connected to %s:%d", self._host, self._port)
                break

            except (IOError, ConnectionRefusedError) as e:
                retries += 1
                if retries > self._retries:
                    raise e

                _LOGGER.warning(
                    f"{e}, attempt {retries}/{self._retries}, retrying in {self.RECONNECT_DELAY} seconds"
                )
                await asyncio.sleep(self._reconnect_delay)

    async def _close_connection(self):
        # Cancel any running reader tasks
        if self._reader_task:
            self._reader_task.cancel()

        # Close and Wait for Stream Writer
        if not self._writer.is_closing():
            self._writer.close()
        await self._writer.wait_closed()

        # Reset Stream Reader and -Writer
        self._reader = self._writer = None

    async def _await_messages(self, timeout: int | None = None):
        """Blocking read messages. Multiple calls await the same StreamReader co-routine."""
        # If there's an in-progress read, wait on it
        if self._reader_task is None or self._reader_task.done():
            # spawn the actual read operation
            self._reader_task = asyncio.create_task(self._perform_read())

        if timeout and timeout > 0:
            res = await asyncio.wait_for(self._reader_task, timeout)
        else:
            res = await self._reader_task
        return res

    async def _perform_read(self):
        """Perform a single read and set the shared future for awaiting coroutines."""
        async with self._reader_lock:
            await self._open_connection()

            MAX_READ = 9 * 100
            data = await self._reader.read(MAX_READ)

            if data == False or data is None or len(data) == 0:
                _LOGGER.warning(
                    "No data received, closing connection, StreamReader=%s",
                    self._reader,
                )
                e = self._reader.exception()
                self._reader = None
                raise IOError("No data received") from e

            decoded_messages = IngeniumBUSingDatagram.decode(data)
            [_LOGGER.debug(f"Decoded message: {msg}") for msg in decoded_messages]

            return decoded_messages

    async def _flush_buffer(self, cb: Callable, delay: None | float):
        """Async flush message buffer content to callback"""
        if not delay is None and delay > 0:
            # Delay a little longer for more messages to arrive
            await asyncio.sleep(delay)

        msgs = self._msg_buffer
        if len(msgs) > 0:
            _LOGGER.debug(f"Flushing {len(msgs)} message(s) from buffer")
            self._msg_buffer = []
            asyncio.create_task(self._do_callback(cb, msgs))

    async def _do_callback(self, cb: Callable, msgs):
        # Trigger callback with message buffer contents
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
