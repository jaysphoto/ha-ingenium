"""Ingenium device, bus devices and HA entities coordination"""

import logging

from enum import Enum
from homeassistant.core import HomeAssistant, dataclass
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)


from .busing.comm import IngeniumBUSingCommunication
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

    AC_GATEWAY_LG = 47
    OTHER = 0


BusDeviceTypeNames = {47: BusDeviceType.AC_GATEWAY_LG.name}


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

    def __init__(self, hass: HomeAssistant, config_entry: dict):
        super().__init__(
            hass,
            _LOGGER,
            name="IngeniumDevice",
        )

        assert CONF_HOST in config_entry.data

        # FIXME: Config entry data types should be defined in a schema and validated, not accessed as dicts
        self._config_entry = config_entry
        self._climate_device_address = None
        self._listener = None

    @property
    def host(self) -> str:
        """Return the host of the ingenium touch device."""
        return self._config_entry.data[CONF_HOST]

    async def async_initialize_device(self) -> bool:
        """Set up the devices for the ingenium touch device or webserver."""

        dr = device_registry.async_get(self.hass)
        dr.async_get_or_create(
            config_entry_id=self._config_entry.entry_id,
            connections={
                (
                    device_registry.CONNECTION_NETWORK_MAC,
                    self._config_entry.data[CONF_MAC],
                )
            },
            # identifiers={
            #     (DOMAIN, api.config.bridge_id),
            #     (DOMAIN, api.config.bridge_device.id),
            # },
            manufacturer=ATTR_MANUFACTURER,
            # name=api.config.name,
            # model_id=api.config.model_id,
            # sw_version=await hass.async_add_executor_job(http.sw_version)
        )

        # Load tracked entities from registry
        existing_entries = entity_registry.async_entries_for_config_entry(
            entity_registry.async_get(self.hass),
            self._config_entry.entry_id,
        )

        _LOGGER.debug("Existing entities for device: %s", existing_entries)

        # TODO: remove stale entities automatically

        self.comm = IngeniumBUSingCommunication(self.host)

        # Setup listener task for BUSing communication
        self._listener = self.hass.async_create_task(
            self.comm.listener(self._bus_message)
        )
        self.hass.data[DOMAIN][self._config_entry.entry_id] = {
            TASK_BUSING: self._listener
        }

    def get_devices(self) -> list[BUSDevice]:
        """Return the devices for the ingenium touch device."""
        return [
            device
            for device in self._all_devices()
            if not self._is_device_ignored(device)
        ]

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
            # BUS register value responses (command: 4)
            if msg["command"] == 4:
                context = (
                    msg["origin"]
                    if msg["destination"] == 0xFEFE
                    else msg["destination"]
                )
                if context not in entity_updates:
                    entity_updates[context] = {"bus_messages": []}
                entity_updates[context]["bus_messages"].append(msg)

        self.async_set_updated_data(entity_updates)
        pass
