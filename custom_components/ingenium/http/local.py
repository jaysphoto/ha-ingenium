import aiohttp
import logging
import re

from typing import Optional
from ..http import IngeniumHttpInstallEntry
from ..exceptions import (
    IngeniumHttpNetworkError,
    IngeniumHttpClientError,
    IngeniumHttpServerError,
)

_LOGGER = logging.getLogger(__name__)


class IngeniumHttpLocal:
    """Class to handle local HTTP requests to Ingenium Gateway."""

    def __init__(self, sess: aiohttp.ClientSession, host: str, port: int = 8000):
        self._sess = sess
        self._host = host
        self._port = port
        self._config = None
        self._install_dat = None
        self._is_v3 = None
        self._sw_version = None

    @property
    async def config(self) -> dict:
        if self._config is None:
            rsp = await self._request("GET", "/CONFIG.TXT")
            conf = await rsp.text()
            p = re.compile(r"^\[(\w+)\] (.*)", re.MULTILINE)
            self._config = dict(p.findall(conf))

            _LOGGER.debug("Parsed config: %s", self._config)

        return self._config

    @property
    async def installation_data(self) -> list[IngeniumHttpInstallEntry]:
        if self._install_dat is None:
            res = await self._request("GET", "/Instal.dat")
            self._install_dat = self._parse_installation_data(await res.text())

        return self._install_dat

    @property
    async def is_v3(self) -> bool:
        if self._is_v3 is None:
            try:
                # Test /v3_0 uri, detects KNX device
                rsp = await self._request("GET", "/v3_0")
                self._is_v3 = len(await rsp.text()) > 0

            except IngeniumHttpClientError as e:
                _LOGGER.debug(
                    "Received error response for /v3_0, assuming non-KNX device: %s",
                    str(e),
                )
                self._is_v3 = False

        return self._is_v3

    @property
    async def sw_version(self) -> str:
        if self._sw_version is None:
            try:
                res = await self._request("GET", "/SiDEVer")
                self._sw_version = await res.text()
            except IngeniumHttpClientError:
                self._sw_version = False
                pass

        return self._sw_version

    def _parse_installation_data(self, data: str):
        """Process device data from /Instal.dat response."""
        _LOGGER.debug("Processing device data:\n%s", data)

        device_info = data.splitlines()
        _LOGGER.info("Found %d entries", len(device_info) / 8)

        res = []
        i = 0
        while i < len(device_info):
            type = int(device_info[i + 6])
            if type > 0:
                res.append(
                    IngeniumHttpInstallEntry(
                        label=device_info[i + 1].strip(),
                        address=int(device_info[i + 4]),
                        output=int(device_info[i + 5]),
                        type=type,
                    )
                )
            i += 8

        return res

    async def _request(
        self, method: str, uri: str, params: Optional[dict] = None
    ) -> aiohttp.ClientResponse:
        """Make API request."""
        _LOGGER.debug("Making API request: %s %s", method, uri)
        try:
            if method == "GET":
                response = await self._sess.get(
                    f"http://{self._host}:{self._port}{uri}", params=params
                )
        except aiohttp.ClientError as e:
            _LOGGER.error(
                "Error occurred while making API request: %s, args:\n%s", str(e), e.args
            )
            raise IngeniumHttpNetworkError

        if 400 <= response.status < 500:
            raise IngeniumHttpClientError
        if 500 <= response.status < 600:
            raise IngeniumHttpServerError

        return response
