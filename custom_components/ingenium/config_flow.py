import async_timeout
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import selector
from typing import Optional

from .const import (
    DOMAIN,
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
                    is_v3 = await http.is_v3()
                    assert is_v3 is False, "Device does appears to be a KNX device"
                    conf = await http.config
                    installation_data = await http.installation_data()

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
                    "device": {CONF_INSTALLATION_DATA: installation_data},
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
        if CONF_IGNORE_AVAILABILITY in user_info:
            self.config[CONF_IGNORE_AVAILABILITY] = user_info[CONF_IGNORE_AVAILABILITY]
            return self.async_create_entry(
                title=f"{ATTR_MANUFACTURER} at {self.config[CONF_HOST]}",
                data=self.config,
            )

        res_ids = []
        for k in self.config["device"][CONF_INSTALLATION_DATA]:
            res_ids.append(k.label)

        cur_ids = []

        _LOGGER.debug("Installation data = %s", res_ids)

        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_IGNORE_AVAILABILITY, default=cur_ids): selector(
                        {"select": {"options": res_ids, "multiple": True}}
                    ),
                }
            ),
        )

    def get_device_http(self, host: str):
        if self.http is None:
            sess = aiohttp_client.async_get_clientsession(self.hass)
            self.http = IngeniumHttpLocal(sess=sess, host=host)
        return self.http
