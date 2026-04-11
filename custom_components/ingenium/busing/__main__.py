"""Use busing as a CLI."""

import argparse
import asyncio
import logging
from xmlrpc import client

from comm import IngeniumBUSingCommunication as busing

LOGGER = logging.getLogger(__name__)


async def main(
    host: str,
    port: int,
) -> None:
    """CLI method for library."""
    LOGGER.info("Starting IngeniumBUSingCommunication")

    client = busing(host, port)
    task = asyncio.create_task(
        client.listener())

    await asyncio.sleep(1)

    # asyncio.create_task(client.send_message(
    #     command=10, origin=0xffff, destination=0xfefe, data1=0, data2=0))

    try:
        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        pass

    finally:
        task.cancel()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("host", type=str)
    parser.add_argument("-p", "--port", type=int, default=busing.DEFAULT_PORT)
    parser.add_argument("-d", "--debug", action="store_true")
    args = parser.parse_args()

    LOG_LEVEL = logging.INFO
    if args.debug:
        LOG_LEVEL = logging.DEBUG
    logging.basicConfig(format="%(message)s", level=LOG_LEVEL)

    asyncio.run(
        main(
            host=args.host,
            port=args.port,
        )
    )
