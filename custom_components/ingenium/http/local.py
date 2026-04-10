import logging
import requests

from typing import List, Optional
from ..device.info import IngeniumDeviceInfo
from ..exceptions import IngeniumHttpNetworkError, IngeniumHttpClientError, IngeniumHttpServerError, IngeniumNotSupportedError

_LOGGER = logging.getLogger(__name__)


class IngeniumHttpLocal:
    """Class to handle local HTTP requests to Ingenium Gateway."""

    def __init__(self, host: str, port: int = 8000):
        self._host = host
        self._port = port

    def devices(self):
        try:
            # Test /v3_0 uri, detects KNX device
            self._request("GET", "/v3_0")

            raise IngeniumNotSupportedError(
                "Detected /v3_0, KNX devices are currently not supported.")

        except IngeniumHttpClientError as e:
            _LOGGER.debug(
                "Received error response for /v3_0, assuming non-KNX device: %s", str(e))

        res = self._request("GET", "/Instal.dat")
        devices = self._process_devices(res.text)

        return devices

    def _process_devices(self, data: str):
        """Process device data from /Instal.dat response."""
        _LOGGER.debug("Processing device data:\n%s", data)

        device_info = data.splitlines()
        _LOGGER.info("Found %d entries", len(device_info) / 9)

        i = 0
        while i < len(device_info):
            label, type, address = device_info[i + 1], int(
                device_info[i + 6]), int(device_info[i + 4])
            if type > 0:
                _LOGGER.debug(
                    "Processing device entry @ %d: label: %s, type %i, address: %i", i, label, type, address)
            i += 8

        # FIXME: return fixed data structure for a single thermostart device for now, until we have a real response to work with
        return [IngeniumDeviceInfo(label="Thermostat", type=8, address=123)]

    def _request(self, method: str, uri: str, params: Optional[dict] = None) -> requests.Response:
        """Make API request."""
        _LOGGER.debug("Making API request: %s %s", method, uri)
        try:
            response = requests.request(
                method,
                f"http://{self._host}:{self._port}{uri}",
                params=params,
            )
        except requests.exceptions.RequestException as e:
            _LOGGER.error(
                "Error occurred while making API request: %s, args:\n%s", str(e), e.args)
            raise IngeniumHttpNetworkError

        if 400 <= response.status_code < 500:
            raise IngeniumHttpClientError
        if 500 <= response.status_code < 600:
            raise IngeniumHttpServerError

        return response
