"""Ingenium device, bus devices and HA entities coordination"""

import logging

from asyncio import Task
from enum import Enum
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, dataclass
from homeassistant.helpers import device_registry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


from .busing.comm import IngeniumBUSingCommunication
from .common import get_identifier_device
from .const import (
    ATTR_MANUFACTURER,
    CONF_DEVICE,
    CONF_HOST,
    CONF_IGNORE_AVAILABILITY,
    CONF_INSTALLATION_DATA,
    CONF_MAC,
    DOMAIN,
    TASK_BUSING,
)

_LOGGER = logging.getLogger(__name__)


class BusDeviceType(Enum):
    """Device types."""

    ACTUATOR_ALL_NOTHING = 24
    AC_GATEWAY_LG = 47

    OTHER = 0


BusDeviceTypeNames = {
    BusDeviceType.AC_GATEWAY_LG.value: BusDeviceType.AC_GATEWAY_LG.name,
    BusDeviceType.ACTUATOR_ALL_NOTHING.value: BusDeviceType.ACTUATOR_ALL_NOTHING.name,
}


@dataclass
class BUSDevice:
    """BUSing device."""

    address: int
    label: str
    device_type: BusDeviceType
    type: int
    output: int


@dataclass
class IgnoredBUSDevice:
    address: int
    type: int
    output: int


"""Class to represent a Ingenium touch device or web server interface and coordinate BUS communication and entities."""


class Device(DataUpdateCoordinator):
    """Class to represent a Ingenium touch device."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name="IngeniumDevice",
        )

        assert CONF_HOST in config_entry.data
        assert CONF_MAC in config_entry.data

        self._config_entry = config_entry
        self._listener = None

    @property
    def host(self) -> str:
        """Return the host of the ingenium touch device."""
        return self._config_entry.data[CONF_HOST]

    @property
    def listener(self) -> None | Task:
        return self._listener

    async def async_initialize_device(self) -> bool:
        """Set up the devices for the ingenium touch device or webserver."""

        entry = self._config_entry

        dr = device_registry.async_get(self.hass)
        dr.async_get_or_create(
            name=f"smart_touch_{entry.data[CONF_MAC]}",
            config_entry_id=entry.entry_id,
            connections={
                (
                    device_registry.CONNECTION_NETWORK_MAC,
                    entry.data[CONF_MAC],
                )
            },
            identifiers={get_identifier_device(entry.data[CONF_MAC])},
            manufacturer=ATTR_MANUFACTURER,
            # name=api.config.name,
            # model_id=api.config.model_id,
            # sw_version=await hass.async_add_executor_job(http.sw_version)
        )

        self.comm = IngeniumBUSingCommunication(self.host)

        # Setup listener task for BUSing communication
        self._listener = self.hass.async_create_background_task(
            self.comm.listener(self._bus_message), f"{DOMAIN}_{TASK_BUSING}"
        )

    def get_devices(self) -> list[BUSDevice]:
        """Return the devices for the ingenium touch device."""
        return [
            device
            for device in self._all_devices()
            if not self._is_device_ignored(device)
        ]

    def get_device_identifiers(self) -> list[dict]:
        """Returns the device identifiers for all currently registered bus devices"""
        identifiers = [(DOMAIN, self._config_entry.data[CONF_MAC])]

        for device in self._config_entry.runtime_configuration["devices"]:
            identifiers.append(
                (DOMAIN, self._config_entry.data[CONF_MAC], device.address, device.type)
            )

        return identifiers

    def _all_devices(self) -> list[BUSDevice]:
        install_config = self._config_entry.data.get(CONF_DEVICE, {}).get(
            CONF_INSTALLATION_DATA, []
        )

        return [
            BUSDevice(
                d["address"],
                d["label"],
                self._device_type(d["type"]),
                d["type"],
                d["output"],
            )
            for d in install_config
        ]

    def _device_type(self, type) -> BusDeviceType:
        if type in BusDeviceTypeNames:
            return BusDeviceType.__getitem__(BusDeviceTypeNames[type])

        return BusDeviceType.OTHER

    def _is_device_ignored(self, d):
        return {
            "type": d.type,
            "output": d.output,
            "address": d.address,
        } in self._config_entry.data.get(CONF_IGNORE_AVAILABILITY, [])

    def _bus_message(self, msgs):
        entity_updates = {}
        for msg in msgs:
            if msg["command"] in [1, 2]:
                # ACK or NACK message
                continue
            elif msg["command"] == 4 and msg["origin"] == 0xFEFE:
                # BUSing device write register value
                context = msg["destination"]
            elif msg["command"] == 4 and msg["origin"] == msg["destination"]:
                # BUSing device register value self-reported value changes
                context = msg["origin"]
            elif msg["command"] == 10 and msg["origin"] == 0xFEFE:
                # Request message for device register value dump
                continue
            else:
                # Unknown, may need further investigation ?
                _LOGGER.debug(
                    f"Ignoring message with: cmd={msg['command']}, destination={msg['destination']}"
                )
                continue

            if context not in entity_updates:
                entity_updates[context] = {"bus_messages": []}

            entity_updates[context]["bus_messages"].append(msg)

        if len(entity_updates) > 0:
            self.async_set_updated_data(entity_updates)
