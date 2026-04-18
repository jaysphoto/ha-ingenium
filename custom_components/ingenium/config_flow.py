import async_timeout
import logging
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import selector
from typing import Optional

from .const import (
    DOMAIN,
    CONF_DEVICE,
    CONF_HOST,
    CONF_INSTALLATION_DATA,
    CONF_IGNORE_AVAILABILITY,
    CONF_MAC,
    CONF_VERSION,
    ATTR_MANUFACTURER,
)
from .exceptions import (
    IngeniumHttpNetworkError,
    IngeniumHttpClientError,
    IngeniumHttpServerError,
)
from .device import IgnoredBUSDevice
from .http.local import IngeniumHttpLocal

_LOGGER = logging.getLogger(__name__)
VERSION = 1


class IngeniumConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ingenium integration config flow."""

    def __init__(self) -> None:
        self.config: dict | None = None
        self.http: IngeniumHttpLocal | None = None

    async def async_step_user(
        self, user_info: Optional[dict] = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step by user."""
        errors = {}
        if user_info is not None:
            try:
                http = self.get_device_http(host=user_info[CONF_HOST])

                async with async_timeout.timeout(5):
                    is_v3 = await http.is_v3
                    assert is_v3 is False, "Device does appears to be a KNX device"
                    conf = await http.config
                    installation_data = await http.installation_data

            except IngeniumHttpNetworkError:
                errors["base"] = "network_error"
            except IngeniumHttpServerError:
                errors["base"] = "server_communication_error"
            except IngeniumHttpClientError:
                errors["base"] = "client_communication_error"
            except AssertionError:
                errors["base"] = "device_not_supported"
            except TimeoutError:
                errors["base"] = "init_timeout"
            else:
                self.config = {
                    CONF_VERSION: VERSION,
                    CONF_HOST: user_info[CONF_HOST],
                    CONF_MAC: conf.get("MAC", "unknown"),
                    CONF_DEVICE: {
                        CONF_INSTALLATION_DATA: [d.copy() for d in installation_data]
                    },
                }
                return await self.async_step_devices(user_info)

        user_info = user_info or {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=user_info.get(CONF_HOST, "")): str}
            ),
            errors=errors,
        )

    async def async_step_devices(self, user_info: Optional[dict]) -> ConfigFlowResult:
        if user_info is not None:
            user_info_ignore_devices = [
                key
                for key in user_info
                if key.startswith(f"{CONF_IGNORE_AVAILABILITY}_type_")
            ]
            if any(user_info_ignore_devices):
                ignored_devices: list[IgnoredBUSDevice] = []

                for key in user_info_ignore_devices:
                    type = key.partition(f"{CONF_IGNORE_AVAILABILITY}_type_")[2]
                    for value in user_info[key][CONF_IGNORE_AVAILABILITY]:
                        _LOGGER.info(f"Found ignored device: {value}")
                        address, _, output = value.partition("-")

                        ignored_devices.append(
                            IgnoredBUSDevice(type=type, address=address, output=output)
                        )

                self.config[CONF_IGNORE_AVAILABILITY] = ignored_devices

                return self.async_create_entry(
                    title=f"{ATTR_MANUFACTURER} at {self.config[CONF_HOST]}",
                    data=self.config,
                )

        devices_by_type: dict[int, list] = {}

        for device in self.config[CONF_DEVICE][CONF_INSTALLATION_DATA]:
            devices_by_type.setdefault(device["type"], []).append(device)

        _LOGGER.debug("Device types = %s", list(devices_by_type.keys()))

        data_schema: dict = {}
        for device_type in sorted(devices_by_type.keys()):
            devices = devices_by_type[device_type]
            options = [
                {
                    "value": f"{device['address']}-{device['output']}",
                    "label": device["label"],
                }
                for device in devices
            ]
            section_key = f"{CONF_IGNORE_AVAILABILITY}_type_{device_type}"

            data_schema[vol.Required(section_key, default={})] = (
                data_entry_flow.section(
                    vol.Schema(
                        {
                            vol.Optional(
                                CONF_IGNORE_AVAILABILITY, default=[]
                            ): selector(
                                {
                                    "select": {
                                        "options": options,
                                        "multiple": True,
                                    }
                                }
                            )
                        }
                    ),
                    {"collapsed": False},
                )
            )

        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema(data_schema),
        )

    def get_device_http(self, host: str):
        if self.http is None:
            sess = aiohttp_client.async_get_clientsession(self.hass)
            self.http = IngeniumHttpLocal(sess=sess, host=host)
        return self.http
