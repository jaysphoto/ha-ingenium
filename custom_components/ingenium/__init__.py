"""Ingenium integration package."""

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry

from .const import DOMAIN, CONF_HOST, CONF_MAC, ATTR_MANUFACTURER, TASK_BUSING
from .busing.comm import IngeniumBUSingCommunication


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    assert CONF_MAC in entry.data

    dr = device_registry.async_get(hass)
    dr.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, entry.data[CONF_MAC])},
        # identifiers={
        #     (DOMAIN, api.config.bridge_id),
        #     (DOMAIN, api.config.bridge_device.id),
        # },
        manufacturer=ATTR_MANUFACTURER,
        # name=api.config.name,
        # model_id=api.config.model_id,
        # sw_version=await hass.async_add_executor_job(http.sw_version)
    )

    # Register the listener task for the bus communication
    comm = IngeniumBUSingCommunication(entry.data[CONF_HOST])
    task = hass.async_create_task(comm.listener())
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
