"""Ingenium integration package."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_HOST, TASK_BUSING
from .busing.comm import IngeniumBUSingCommunication


async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    comm = IngeniumBUSingCommunication(host)
    task = hass.async_create_task(
        comm.listener()
    )
    hass.data[DOMAIN][entry.entry_id] = {TASK_BUSING: task}
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data and TASK_BUSING in data:
        data[TASK_BUSING].cancel()
        try:
            await data[TASK_BUSING]
        except BaseException:
            pass
    return True
