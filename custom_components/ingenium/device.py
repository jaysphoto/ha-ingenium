"""Ingenium device, bus devices and HA entities coordination"""

import asyncio
import async_timeout
import logging

from asyncio import Task
from datetime import timedelta
from enum import Enum
from typing import Callable
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, dataclass
from homeassistant.helpers import device_registry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


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
            update_interval=timedelta(
                seconds=IngeniumBUSingCommunication.DEFAULT_POLLING_INTERVAL
            ),
        )

        assert CONF_HOST in config_entry.data
        assert CONF_MAC in config_entry.data

        self._config_entry = config_entry
        self._comm = IngeniumBUSingCommunication(self.host)
        self._listener = None
        self._sync_request_ack_event = asyncio.Event()
        self._sync_last_response_msg = None
        self._background_listener_timeout = timedelta(seconds=300)

    @property
    def host(self) -> str:
        """Return the host of the ingenium touch device."""
        return self._config_entry.data[CONF_HOST]

    @property
    def listener(self) -> None | Task:
        return self._listener

    @property
    def comm(self) -> IngeniumBUSingCommunication:
        return self._comm

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

        try:
            await self._comm._open_connection()

            # (Optional) background listener task for BUSing communication
            if self._background_listener_timeout is not None:
                self._listener = self.hass.async_create_background_task(
                    self._async_background_listener(
                        self._background_listener_timeout.total_seconds()
                    ),
                    f"{DOMAIN}_{TASK_BUSING}",
                )

                # First time get all device registers
                await self._trigger_bus_device_report()
        except Exception as e:
            raise UpdateFailed(f"Error initializing Ingenium device: {e}")

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

    async def _async_background_listener(self, timeout: int):
        """Endless loop waiting for BUSIng messages to arrive and process"""
        while True:
            try:
                """
                    Ingenium BUSing connection closes itself around ~ 7 minutes (reasons unknown).
                    We run the BUSing listener until the timeout, then close the connection and repeat.
                """
                async with async_timeout.timeout(timeout):
                    await self._comm.listener(self._bus_message)

            except asyncio.TimeoutError:
                await self._comm._close_connection()

            except asyncio.CancelledError:
                # Background task was cancelled, probably hass shutdown or integration reload
                break

    async def _async_update_data(self):
        """
        Async update method called by hass every self.update_interval seconds. This timer is also reset
        by the _async_background_listener, when it receives data. If there is BUSing data received by that
        loop at regular intervals, this method may never get called.

        It serves as a fallback if the data "PULL" mechanism fails, or the integration can be put in a
        PULL-only mode entirely.
        """
        _LOGGER.info("Triggering _async_update_data device register report")

        def validate_response(msg):
            if msg == None or msg["command"] == 2:
                raise UpdateFailed(f"Received invalid or NACK response: {msg}")

        try:
            listener_task = None

            async with async_timeout.timeout(15):
                self._sync_last_response_msg = None
                self._sync_request_ack_event.clear()

                # Create a listener co-routine if the hass background task isn't already running
                if self.listener == None or self.listener.done():
                    listener_task = asyncio.create_task(
                        self._comm.listener(self._bus_message)
                    )
                    _LOGGER.debug("Listener created")
                else:
                    _LOGGER.info("Background Listener Task: %s", self.listener)

                await self._trigger_bus_device_report(cb=self._bus_device_report_ack)

                # Wait for ACK response to arrive at callback method and validate
                await self._sync_request_ack_event.wait()
                _LOGGER.debug("Received first _bus_device_report_ack callback")
                validate_response(self._sync_last_response_msg)

                # Await and validate second (closing) ACK message
                res = await self._comm.await_response(origin=0xFF)
                _LOGGER.debug("Received closing response message")
                validate_response(res)

                # Data sent to Entities for processing. We rely on the listener Co-routine instead for that job.
                return {}
        except (asyncio.TimeoutError, TimeoutError) as err:
            raise UpdateFailed(f"Communication Timeout: {err}")
        except IOError as err:
            raise UpdateFailed(f"Error communicating: {err}")
        finally:
            if listener_task is not None:
                listener_task.cancel()
                _LOGGER.debug("Listener cancelled")

    async def _trigger_bus_device_report(self, cb: Callable | None = None) -> None:
        await self._comm.send_message(
            destination=0xFF, command=10, data1=0, data2=0, cb=cb
        )

    def _bus_device_report_ack(self, msg) -> None:
        self._sync_last_response_msg = msg
        self._sync_request_ack_event.set()

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
