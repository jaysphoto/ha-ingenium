import logging
import requests

from typing import List, Optional
from ..device.info import IngeniumDeviceInfo
from ..exceptions import IngeniumHttpNetworkError, IngeniumHttpClientError, IngeniumHttpServerError

_LOGGER = logging.getLogger(__name__)


class IngeniumHttpLocal:
    """Class to handle local HTTP requests to Ingenium Gateway."""

    def __init__(self, host: str = '192.168.103.91', port: int = 8000):
        self._host = host
        self._port = port

    def devices(self) -> List[IngeniumDeviceInfo]:
        res = self._request("GET", "/Instal.dat")
        _LOGGER.debug("Received response: %s", res.text)
        res = self._request("GET", "/v3_0")
        return [IngeniumDeviceInfo(serial="123456789", credential="credential")]

    def _request(
        self,
        method: str,
        uri: str,
        params: Optional[dict] = None,
    ) -> requests.Response:
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
