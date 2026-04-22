"""Ingenium BUSDevice Entity base class"""

import logging

from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from typing import final

from .const import ATTR_MANUFACTURER, DOMAIN, CONF_MAC
from .device import Device

_LOGGER = logging.getLogger(__name__)


class BaseEntity(CoordinatorEntity, Entity):
    def __init__(self, config_entry: dict, dev: Device, model: str = None):
        super().__init__(config_entry.runtime_configuration["coordinator"])

        self._parent_config_entry = config_entry
        self._attr_has_entity_name = True
        self._address = dev.address
        self._model = model

    @final
    def _handle_coordinator_update(self) -> None:
        if self._address not in self.coordinator.data:
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

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._parent_config_entry.data[CONF_MAC], self._address)
            },
            name=f"smart_touch_{self._parent_config_entry.data[CONF_MAC]}_{self._address}",
            manufacturer=ATTR_MANUFACTURER,
            model=self._model,
            via_device=(DOMAIN, self._parent_config_entry.data[CONF_MAC]),
        )
