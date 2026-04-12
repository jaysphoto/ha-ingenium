import aiohttp
import logging
import re

from typing import List, Optional
from ..device import IngeniumDeviceInfo
from ..exceptions import IngeniumHttpNetworkError, IngeniumHttpClientError, IngeniumHttpServerError

_LOGGER = logging.getLogger(__name__)


class IngeniumHttpLocal:
    """Class to handle local HTTP requests to Ingenium Gateway."""

    def __init__(self, sess: aiohttp.ClientSession, host: str, port: int = 8000):
        self._sess = sess
        self._host = host
        self._port = port
        self._config = None

    @property
    async def config(self) -> dict:
        if self._config is None:
            rsp = await self._request("GET", "/CONFIG.TXT")
            conf = await rsp.text()
            p = re.compile(r"^\[(\w+)\] (.*)", re.MULTILINE)
            self._config = dict(p.findall(conf))

            _LOGGER.debug("Parsed config: %s", self._config)

        return self._config

    async def devices(self) -> List:
        res = await self._request("GET", "/Instal.dat")
        devices = self._process_devices(await res.text())

        return devices

    async def is_v3(self) -> bool:
        try:
            # Test /v3_0 uri, detects KNX device
            rsp = await self._request("GET", "/v3_0")
            return len(await rsp.text()) > 0

        except IngeniumHttpClientError as e:
            _LOGGER.debug(
                "Received error response for /v3_0, assuming non-KNX device: %s", str(e))

        return False

    async def sw_version(self) -> str:
        ver = 'unknown'
        try:
            res = await self._request("GET", "/SiDEVer")
            ver = await res.text() or ver
        except IngeniumHttpClientError:
            pass

        return ver

    def _process_devices(self, data: str):
        """Process device data from /Instal.dat response."""
        _LOGGER.debug("Processing device data:\n%s", data)

        device_info = data.splitlines()
        _LOGGER.info("Found %d entries", len(device_info) / 8)

        i = 0
        while i < len(device_info):
            label, type, address = device_info[i + 1], int(
                device_info[i + 6]), int(device_info[i + 4])
            if type > 0:
                _LOGGER.debug(
                    "Processing device entry @ %d: label: %s, type %i, address: %i", i, label, type, address)
            i += 8

        # TODO: return fixed data structure for a single thermostart device for now, until we have a real response to work with
        return [IngeniumDeviceInfo(label="AC GENERAL", type=47, address=11)]

    async def _request(self, method: str, uri: str, params: Optional[dict] = None) -> aiohttp.ClientResponse:
        """Make API request."""
        _LOGGER.debug("Making API request: %s %s", method, uri)
        try:
            if method == "GET":
                response = await self._sess.get(f"http://{self._host}:{self._port}{uri}", params=params)
        except aiohttp.ClientError as e:
            _LOGGER.error(
                "Error occurred while making API request: %s, args:\n%s", str(e), e.args)
            raise IngeniumHttpNetworkError

        if 400 <= response.status < 500:
            raise IngeniumHttpClientError
        if 500 <= response.status < 600:
            raise IngeniumHttpServerError

        return response
