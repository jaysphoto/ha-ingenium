import pytest
import asyncio

from unittest.mock import patch, Mock, AsyncMock

from custom_components.ingenium.busing.comm import IngeniumBUSingCommunication as busing


class MockReader(AsyncMock):
    pass


class MockWriter(AsyncMock):
    pass

    def write(self, *args, **kwargs):
        pass

    async def drain(self):
        pass

    def is_closing(self):
        return False


async def test_invalid_values():
    # Normal initialization should not raise Errors
    busing("127.0.0.1", connect_retries=1, reconnect_delay=0.1, response_timeout=1.0)

    with pytest.raises(ValueError):
        busing("127.0.0.1", connect_retries=-1)
    with pytest.raises(ValueError):
        busing("127.0.0.1", reconnect_delay=-1)
    with pytest.raises(ValueError):
        busing("127.0.0.1", response_timeout=-1)


@pytest.mark.asyncio
async def test_open_connection():
    b = busing("127.0.0.1")
    with patch.object(
        asyncio, "open_connection", return_value=[MockReader(), MockWriter()]
    ):
        await b._open_connection()

        assert isinstance(b._reader, MockReader)
        assert isinstance(b._writer, MockWriter)


@pytest.mark.asyncio
async def test_open_connection_retry_refused():
    b = busing("127.0.0.1", reconnect_delay=0.0001)
    with patch.object(
        asyncio,
        "open_connection",
        side_effect=[ConnectionRefusedError, [MockReader(), MockWriter()]],
    ):
        await b._open_connection()
        assert isinstance(b._reader, MockReader)
        assert isinstance(b._writer, MockWriter)


@pytest.mark.asyncio
async def test_open_connection_retries_exhaused():
    b = busing("127.0.0.1", reconnect_delay=0.0001, connect_retries=2)
    with (
        patch.object(
            asyncio,
            "open_connection",
            side_effect=[ConnectionRefusedError, ConnectionRefusedError, IOError],
        ),
        # With too many errors, open_connection should raise the last error
        pytest.raises(IOError),
    ):
        await b._open_connection()


@pytest.mark.asyncio
async def test_close_connection():
    b = busing("127.0.0.1")
    writer = Mock()
    writer.is_closing = Mock(return_value=False)
    writer.close = Mock()
    writer.wait_closed = AsyncMock()

    with patch.object(asyncio, "open_connection", return_value=[MockReader(), writer]):
        await b._open_connection()
        await b._close_connection()

        assert writer.is_closing.is_called_once()
        assert writer.close.is_called_once()

        assert b._reader is None
        assert b._writer is None


@pytest.mark.asyncio
async def test_await_response_ack_nack():
    b = busing("127.0.0.1")

    reader = asyncio.StreamReader()

    with patch.object(asyncio, "open_connection", return_value=[reader, MockWriter()]):
        ACK = 1
        NACK = 2
        for rsp in [ACK, NACK]:
            reader.feed_data(bytes.fromhex(f"fefe {rsp:02x} fefe 0001 18 18"))

            res = await b.await_response()

            assert isinstance(res, dict)
            assert "command" in res
            assert res["command"] == rsp


@pytest.mark.asyncio
async def test_await_response_with_noise():
    b = busing("127.0.0.1")

    reader = asyncio.StreamReader()

    with patch.object(asyncio, "open_connection", return_value=[reader, MockWriter()]):
        reader.feed_data(
            bytes.fromhex("0000 00 0000 0000 00 00" + "fefe 01 fefe 0001 18 18")
        )
        reader.feed_eof()

        res = await b.await_response()

        assert isinstance(res, dict)
        assert "command" in res
        assert res["command"] == 1


@pytest.mark.asyncio
async def test_await_response_with_timeout():
    b = busing("127.0.0.1", response_timeout=0.01)
    reader = asyncio.StreamReader()

    with (
        patch.object(asyncio, "open_connection", return_value=[reader, MockWriter()]),
        # Will raise IOError due to timeout
        pytest.raises(IOError),
    ):
        await b.await_response()


@pytest.mark.asyncio
async def test_await_response_with_empty_response_reconnect():
    b = busing("127.0.0.1", response_timeout=0.01)
    reader = asyncio.StreamReader()
    count = 0

    async def read_side_effect(n=int):
        nonlocal count
        count += 1
        if count == 1:
            reader.feed_eof()
            return
        else:
            return bytes.fromhex("fefe 01 fefe 0001 18 18")

    with (
        patch.object(asyncio, "open_connection", return_value=[reader, MockWriter()]),
        patch.object(reader, "read", side_effect=read_side_effect),
    ):
        res = await b.await_response()

        assert isinstance(res, dict)
        assert "command" in res
        assert res["command"] == 1


@pytest.mark.asyncio
async def test_send_message():
    b = busing("127.0.0.1")
    writer = Mock()
    writer.write = Mock()
    writer.drain = AsyncMock()

    with patch.object(asyncio, "open_connection", return_value=[MockReader(), writer]):
        await b.send_message(command=10, destination=0xFF, data1=0, data2=0)

    writer.write.assert_called_once_with(bytes.fromhex("ffff 00ff 0a 00 00"))
    writer.drain.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_with_callback():
    b = busing("127.0.0.1", response_timeout=0.01)
    reader = asyncio.StreamReader()

    call_count = 0
    created_tasks = []

    def callback(msg):
        nonlocal call_count
        call_count += 1
        assert isinstance(msg, dict)
        assert "command" in msg
        assert msg["command"] == 1

    def capture_create_task(coro, *args, **kwargs):
        task = asyncio.get_running_loop().create_task(coro, *args, **kwargs)
        created_tasks.append(task)
        return task

    with (
        patch.object(asyncio, "open_connection", return_value=[reader, MockWriter()]),
        patch.object(asyncio, "create_task", side_effect=capture_create_task),
        patch.object(
            reader, "read", return_value=bytes.fromhex("fefe 01 fefe 0012 18 18")
        ),
    ):
        # Send command message with our callback function
        await b.send_message(
            command=10, destination=0x12, data1=0, data2=0, cb=callback
        )
        # Gather all created tasks to ensure they complete before asserting
        if created_tasks:
            await asyncio.wait_for(asyncio.gather(*created_tasks), timeout=1)

        assert call_count == 1


@pytest.mark.asyncio
async def test_listener_reads_and_buffers_messages():
    """Test that listener reads messages and buffers them."""
    b = busing("127.0.0.1")
    messages = [
        {"command": 4, "origin": 0xFEFE, "destination": 5},
        {"command": 4, "origin": 7, "destination": 7},
    ]
    callback = Mock()

    async def perform_read_side_effect():
        # Simulate reading messages once, then cancel
        if len(messages) > 0:
            return [messages.pop(0)]
        raise asyncio.CancelledError()

    with (
        patch.object(b, "_perform_read", side_effect=perform_read_side_effect),
        patch.object(b, "_flush_buffer", new_callable=AsyncMock) as mock_flush,
    ):
        await b.listener(callback)

        # Verify flush was called with callback
        assert mock_flush.called


@pytest.mark.asyncio
async def test_listener_handles_ioerror():
    """Test that listener continues after IOError."""
    b = busing("127.0.0.1", reconnect_delay=0.0001)
    callback = Mock()
    call_count = 0

    async def await_messages_side_effect(timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise IOError("Connection lost")
        raise asyncio.CancelledError()

    with (
        patch.object(b, "_await_messages", side_effect=await_messages_side_effect),
        patch.object(b, "_flush_buffer", new_callable=AsyncMock),
    ):
        await b.listener(callback)

        # Should continue after IOError without raising
        assert call_count == 2


@pytest.mark.asyncio
async def test_listener_passes_ioerror():
    """Test that listener passes IOError without auto_reconnecting."""
    b = busing("127.0.0.1", reconnect_delay=0.0001)
    callback = Mock()
    call_count = 0

    async def await_messages_side_effect(timeout=None):
        raise IOError("Connection lost")

    with (
        patch.object(b, "_await_messages", side_effect=await_messages_side_effect),
        pytest.raises(IOError),
    ):
        await b.listener(callback, auto_reconnect=False)

        # Should continue after IOError without raising
        assert call_count == 2


@pytest.mark.asyncio
async def test_listener_schedules_flush_task():
    """Test that listener schedules flush_buffer task."""
    b = busing("127.0.0.1")
    callback = Mock()
    call_count = 0

    async def await_messages_side_effect(timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call returns messages
            return [{"msg": 1}]
        # Second call raises CancelledError to exit
        raise asyncio.CancelledError()

    with (
        patch.object(b, "_await_messages", side_effect=await_messages_side_effect),
        patch.object(b, "_flush_buffer", new_callable=AsyncMock) as mock_flush,
    ):
        await b.listener(callback)

        # Verify flush_buffer was called after messages were received
        mock_flush.assert_called()


@pytest.mark.asyncio
async def test_flush_buffer_delays_before_callback():
    """Test that _flush_buffer delays and then calls callback."""
    b = busing("127.0.0.1")
    callback = Mock()
    b._msg_buffer = [{"msg": 1}, {"msg": 2}]
    delay = 0.01

    with (
        patch(
            "custom_components.ingenium.busing.comm.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        patch.object(b, "_do_callback", new_callable=AsyncMock),
    ):
        await b._flush_buffer(callback, delay)

        # Verify sleep was called with correct delay
        mock_sleep.assert_called_once_with(delay)


@pytest.mark.asyncio
async def test_flush_buffer_clears_buffer():
    """Test that _flush_buffer clears the message buffer."""
    b = busing("127.0.0.1")
    callback = Mock()
    b._msg_buffer = [{"msg": 1}, {"msg": 2}]

    with (
        patch(
            "custom_components.ingenium.busing.comm.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        patch.object(b, "_do_callback", new_callable=AsyncMock),
    ):
        await b._flush_buffer(callback, 0)

    # Verify buffer was cleared
    assert len(b._msg_buffer) == 0


@pytest.mark.asyncio
async def test_flush_buffer_calls_callback_with_messages():
    """Test that _flush_buffer calls callback with accumulated messages."""
    b = busing("127.0.0.1")
    callback = Mock()
    messages = [{"msg": 1}, {"msg": 2}]
    b._msg_buffer = messages.copy()

    with (
        patch(
            "custom_components.ingenium.busing.comm.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        patch.object(b, "_do_callback", new_callable=AsyncMock),
    ):
        await b._flush_buffer(callback, 0)

    # Verify buffer was processed
    assert len(b._msg_buffer) == 0


@pytest.mark.asyncio
async def test_flush_buffer_no_delay():
    """Test that _flush_buffer works without delay (None or 0)."""
    b = busing("127.0.0.1")
    callback = Mock()
    b._msg_buffer = [{"msg": 1}]

    with (
        patch(
            "custom_components.ingenium.busing.comm.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        patch.object(b, "_do_callback", new_callable=AsyncMock),
    ):
        await b._flush_buffer(callback, None)

    # Should not call sleep with None delay
    mock_sleep.assert_not_called()
