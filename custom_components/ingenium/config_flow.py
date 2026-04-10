import logging
import voluptuous as vol

from homeassistant import config_entries
from typing import Optional

from .const import DOMAIN, CONF_HOST
from .exceptions import IngeniumHttpNetworkError, IngeniumHttpClientError, IngeniumHttpServerError
from .http.local import IngeniumHttpLocal

_LOGGER = logging.getLogger(__name__)


class IngeniumConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Ingenium integration config flow."""

    async def async_step_user(self, info: Optional[dict] = None):
        """Handle the initial setup step by user."""
        errors = {}
        if info is not None:
            try:
                client = IngeniumHttpLocal(host=info[CONF_HOST])

                _devices = await self.hass.async_add_executor_job(
                    client.devices
                )
            except IngeniumHttpNetworkError:
                errors["base"] = "network_error"
            except IngeniumHttpServerError:
                errors["base"] = "server_communication_error"
            except IngeniumHttpClientError:
                errors["base"] = "client_communication_error"
            else:
                self._host = info[CONF_HOST]
                _LOGGER.info("Detected %d connected devices on %s",
                             len(_devices), info[CONF_HOST])

                return self.async_create_entry(title=info["host"], data=info)

        info = info or {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=info.get(CONF_HOST, "")): str
            }),
            errors=errors,
        )

    # async def async_step_ingenium_config(self, info: Optional[dict] = None):
        # await self.async_set_unique_id(serial_number)
        # self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
