"""Ingenium BUSDevice Entity base class"""

import logging

from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from typing import final

from .const import ATTR_MANUFACTURER, DOMAIN, CONF_MAC
from .common import get_identifier_entity
from .device import Device
from . import IngeniumConfigEntry

_LOGGER = logging.getLogger(__name__)


class BaseEntity(CoordinatorEntity, Entity):
    def __init__(
        self, config_entry: IngeniumConfigEntry, dev: Device, model: str = None
    ):
        super().__init__(config_entry.runtime_configuration["coordinator"])

        self._parent_config_entry = config_entry
        self._attr_has_entity_name = True
        self._address = dev.address
        self._type_id = dev.type
        self._model = model

    @final
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data == None or self._address not in self.coordinator.data:
            return

        service_call = self.coordinator.data[self._address]

        res = [
            self._read_bus_message(msg)
            for msg in service_call["bus_messages"]
            if msg["command"] == 4
            if "bus_messages" in service_call
            if self._bus_message_filter(msg)
        ]
        # Request update of HA state if any message resulted in an update to the entity state
        if any(res):
            _LOGGER.debug(f"Updated Entity state for {self}")
            self.async_write_ha_state()

    def _bus_message_filter(self, msg) -> bool:
        """Method that determines which messages pass for processing"""
        return True

    def _read_bus_message(self, msg) -> bool:
        pass

    async def _send_bus_message(self, command: int, data1: int, data2: int) -> None:
        """Send a message to the bus via the coordinator"""
        await self.coordinator.comm.send_message(
            destination=self._address,
            command=command,
            data1=data1,
            data2=data2,
            cb=self._process_response_message,
        )

    def _process_response_message(self, msg) -> None:
        """Process a response message from the bus"""
        if msg["command"] == 1:
            if self._bus_message_filter(msg) and self._read_bus_message(msg):
                _LOGGER.debug(f"Updated Entity state for {self} : {msg}")
                self.async_write_ha_state()
        else:
            _LOGGER.warning(
                f"Received response message for {self} but no state change: {msg}"
            )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Touch device MAC, bus address and bus device type id are unique
                get_identifier_entity(
                    mac=self._parent_config_entry.data[CONF_MAC],
                    address=self._address,
                    type=self._type_id,
                )
            },
            name=f"smart_touch_{self._parent_config_entry.data[CONF_MAC]}_{self._address}",
            manufacturer=ATTR_MANUFACTURER,
            model=self._model,
            via_device=(DOMAIN, self._parent_config_entry.data[CONF_MAC]),
        )
