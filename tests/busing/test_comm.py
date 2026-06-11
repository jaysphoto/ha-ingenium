import pytest
import asyncio

from unittest.mock import patch, Mock, AsyncMock

from custom_components.ingenium.busing.comm import IngeniumBUSingCommunication as busing


class MockReader(AsyncMock):
    pass


class MockWriter(AsyncMock):
    pass


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
async def test_send_message():
    b = busing("127.0.0.1")
    writer = Mock()
    writer.write = Mock()
    writer.drain = AsyncMock()

    with patch.object(asyncio, "open_connection", return_value=[MockReader(), writer]):
        await b.send_message(command=10, destination=0xFF, data1=0, data2=0)

    writer.write.assert_called_once_with(bytes.fromhex("ffff 00ff 0a 00 00"))
    writer.drain.assert_awaited_once()
