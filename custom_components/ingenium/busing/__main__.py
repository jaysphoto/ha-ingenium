"""Use BUSing as a CLI."""

import argparse
import asyncio
import logging

from comm import IngeniumBUSingCommunication as busing

_LOGGER = logging.getLogger(__name__)


async def main(host: str, port: int, raw_msg: str | None, bus_init=bool) -> None:
    """CLI method for library."""
    _LOGGER.info("Starting IngeniumBUSingCommunication")

    client = busing(host, port)

    if raw_msg is not None:
        """
        Single raw command mode, examples:

        asyncio.create_task(client.send_message_raw(
            command=10, origin=-1, destination=-1, data1=0, data2=0)) -> ffffffff0a0000 # READ ALL REGISTERS, ALL DEVICES
                Received datagram: {'raw': 'fefe01fefe00ff0000', 'command': 1, 'origin': 65278, 'destination': 255, 'data1': 0, 'data2': 0}
                Received datagram: {'raw': 'fefe04000100010120', 'command': 4, 'origin': 1, 'destination': 1, 'data1': 1, 'data2': 32}
                Received datagram: {'raw': 'fefe0400010001ff01', 'command': 4, 'origin': 1, 'destination': 1, 'data1': 255, 'data2': 1}
                Received datagram: {'raw': 'fefe04000b000b0002', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 0, 'data2': 2}
                Received datagram: {'raw': 'fefe04000b000b0113', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 1, 'data2': 19}
                ....
            command=3, origin=-1, destination=1, data1=1, data2=1)) -> ffff0001030101. # READ STATUS OF SWITCH DEVICE (Actuador)
                Received datagram: {'raw': 'fefe01fefe00012020', 'command': 1, 'origin': 65278, 'destination': 1, 'data1': 32, 'data2': 32}
            command=10, origin=-1, destination=11, data1=0, data2=0 -> ffff000b0a0000. # READ ALL REGISTERS OF AC GATEWAY (Termostato)
                Received datagram: {'raw': 'fefe04000b000b0002', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 0, 'data2': 2}
                Received datagram: {'raw': 'fefe04000b000b0113', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 1, 'data2': 19}
                Received datagram: {'raw': 'fefe04000b000b0208', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 2, 'data2': 8}
                Received datagram: {'raw': 'fefe04000b000b0400', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 4, 'data2': 0}
                ...
                Received datagram: {'raw': 'fefe04000b000b3e00', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 62, 'data2': 0}
                Received datagram: {'raw': 'fefe04000b000bff01', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 255, 'data2': 1}
                Received datagram: {'raw': 'fefe01fefe000b0101', 'command': 1, 'origin': 65278, 'destination': 11, 'data1': 0, 'data2': 0}
        """
        await client.send_message_raw(bytes.fromhex(raw_msg))
        response = await client.await_response()
        _LOGGER.info("Received response: %s", response)

        return

    # Send request to dump all device registers on the BUSing interface
    if bus_init:
        # await client.send_message_raw(bytes.fromhex('ffffffff0a0000'))
        await client.send_message(
            _origin=0xFFFF, destination=0xFFFF, command=10, data1=0, data2=0
        )

    try:
        # Start the listener task and loop forever
        await client.listener(
            lambda msgs: [_LOGGER.info("Received message: %s", msg) for msg in msgs]
        )

    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("host", type=str)
    parser.add_argument("-p", "--port", type=int, default=busing.DEFAULT_PORT)
    parser.add_argument(
        "-r",
        "--raw",
        type=str,
        default=None,
        dest="raw_msg",
        help="Send a single raw command and await response message (hex string, e.g. ffff0001030101)",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Show debug log messages"
    )
    parser.add_argument(
        "--bus-init",
        action="store_true",
        help="Send request for all bus/device registers",
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(
            format="%(name)s - %(levelname)s: %(message)s", level=logging.DEBUG
        )
    else:
        logging.basicConfig(format="%(message)s", level=logging.INFO)

    asyncio.run(
        main(
            host=args.host, port=args.port, raw_msg=args.raw_msg, bus_init=args.bus_init
        )
    )
