"""Use BUSing as a CLI."""

import argparse
import asyncio
import logging

from comm import IngeniumBUSingCommunication as busing

_LOGGER = logging.getLogger(__name__)


async def main(
    host: str,
    port: int,
    raw_msg: str | None,
    listen=bool,
    bus_init=bool,
    polling_interval: int | None = None,
) -> None:
    _LOGGER.info("Starting IngeniumBUSingCommunication")

    task_queue = asyncio.Queue()

    client = busing(host, port)
    await client._open_connection()

    if bus_init:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(poll_bus_devices(client))
            _LOGGER.info("Polling for BUSing device status once")

    if raw_msg is not None:
        async with asyncio.TaskGroup() as tg:
            """
            Single raw command mode, examples:

            asyncio.create_task(client.send_message(
                # READ ALL REGISTERS, ALL DEVICES
                command=10, destination=-1, data1=0, data2=0)) -> ffffffff0a0000
                    Received datagram: {'raw': 'fefe01fefe00ff0000', 'command': 1, 'origin': 65278, 'destination': 255, 'data1': 0, 'data2': 0}
                    Received datagram: {'raw': 'fefe04000100010120', 'command': 4, 'origin': 1, 'destination': 1, 'data1': 1, 'data2': 32}
                    Received datagram: {'raw': 'fefe0400010001ff01', 'command': 4, 'origin': 1, 'destination': 1, 'data1': 255, 'data2': 1}
                    Received datagram: {'raw': 'fefe04000b000b0002', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 0, 'data2': 2}
                    Received datagram: {'raw': 'fefe04000b000b0113', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 1, 'data2': 19}
                    ....
                # READ STATUS OF SWITCH DEVICE (Actuador)
                command=3, destination=1, data1=1, data2=1)) -> ffff0001030101
                    Received datagram: {'raw': 'fefe01fefe00012020', 'command': 1, 'origin': 65278, 'destination': 1, 'data1': 32, 'data2': 32}
                # ENABLE OUTPUT 5 SWITCH DEVICE (Actuador)
                command=4, destination=1, data1=2, data2=5)) -> ffff0001040205
                    Received response: {'raw': 'fefe01fefe00010205', 'command': 1, 'origin': 65278, 'destination': 1, 'data1': 2, 'data2': 5}
                # DISABLE OUTPUT 5 SWITCH DEVICE (Actuador)
                command=4, destination=1, data1=2, data2=13)) -> ffff000104020d
                    Received response: {'raw': 'fefe01fefe0001020d', 'command': 1, 'origin': 65278, 'destination': 1, 'data1': 2, 'data2': 13}
                # DIAGNOSTIC COMMAND FOR SWITCH DEVICE (Actuador)
                command=9, destination=1, data1=0, data2=0)) -> ffff0001090000
                    Received response: {'raw': 'fefe01fefe00011818', 'command': 1, 'origin': 1, 'destination': 65278, 'data1': 24, 'data2': 2
                # READ ALL REGISTERS OF AC GATEWAY (Termostato)
                command=10, destination=11, data1=0, data2=0 -> ffff000b0a0000
                    Received datagram: {'raw': 'fefe04000b000b0002', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 0, 'data2': 2}
                    Received datagram: {'raw': 'fefe04000b000b0113', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 1, 'data2': 19}
                    Received datagram: {'raw': 'fefe04000b000b0208', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 2, 'data2': 8}
                    Received datagram: {'raw': 'fefe04000b000b0400', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 4, 'data2': 0}
                    ...
                    Received datagram: {'raw': 'fefe04000b000b3e00', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 62, 'data2': 0}
                    Received datagram: {'raw': 'fefe04000b000bff01', 'command': 4, 'origin': 11, 'destination': 11, 'data1': 255, 'data2': 1}
                    Received datagram: {'raw': 'fefe01fefe000b0101', 'command': 1, 'origin': 65278, 'destination': 11, 'data1': 0, 'data2': 0}
            """
            tg.create_task(
                client.send_message_raw(bytes.fromhex(raw_msg))
            )

    if listen or polling_interval is not None:
        """BUSing polling and listen operations both run until cancelled """
        try:
            async with asyncio.TaskGroup() as tg:
                if polling_interval is not None and polling_interval > 0:

                    async def polling_periodically(interval: int):
                        while True:
                            await asyncio.sleep(interval)
                            await poll_bus_devices()

                    # Schedule polling messages at the configured interval
                    tg.create_task(polling_periodically(polling_interval))
                    _LOGGER.info(
                        "Polling for BUSing device status every %i second(s).",
                        polling_interval,
                    )

                # Start the listener task and loop forever
                if listen:
                    tg.create_task(
                        client.listener(
                            lambda msgs: [
                                _LOGGER.info("Received message: %s", msg)
                                for msg in msgs
                            ]
                        )
                    )
                    _LOGGER.info("Listening for BUSing messages")
        except asyncio.CancelledError:
            pass

    # Execute and wait for task queue to complete
    await task_queue.join()


async def poll_bus_devices(client: busing):
    _LOGGER.info(
        "Sending BUSing report request (command=10, origin=-1, destination=-1, data1=0, data2=0)"
    )
    await client.send_message(
        destination=0xFFFF,
        command=10,
        data1=0,
        data2=0,
        cb=lambda msg: _LOGGER.info(
            "BUSing command message success: %s", msg["command"] == 1
        ),
    )


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
        "--listen",
        action="store_true",
        help="Start listener for incoming messages (e.g. for monitoring BUSing traffic)",
    )
    parser.add_argument(
        "--bus-init",
        action="store_true",
        help="Send request for all bus/device registers",
    )
    parser.add_argument(
        "--polling",
        type=int,
        nargs="?",
        default=None,
        const=busing.DEFAULT_POLLING_INTERVAL,
        metavar="INTERVAL",
        dest="polling",
        help=f"Poll bus devices at interval in seconds (default: {busing.DEFAULT_POLLING_INTERVAL})",
    )

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(
            format="%(asctime)s %(name)s - %(levelname)s: %(message)s",
            level=logging.DEBUG,
        )
    else:
        logging.basicConfig(format="%(message)s", level=logging.INFO)

    asyncio.run(
        main(
            host=args.host,
            port=args.port,
            raw_msg=args.raw_msg,
            bus_init=args.bus_init,
            listen=args.listen,
            polling_interval=args.polling,
        )
    )
