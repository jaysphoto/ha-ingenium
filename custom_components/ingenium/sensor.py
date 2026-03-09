"""Basic sensor platform for Ingenium example."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_NAME


async def async_setup_platform(hass: HomeAssistant, config, async_add_entities: AddEntitiesCallback, discovery_info=None):
    """Set up the Ingenium sensor platform."""
    async_add_entities([IngeniumSensor()])


class IngeniumSensor(SensorEntity):
    def __init__(self):
        self._state = None
        self._attr_name = DEFAULT_NAME

    @property
    def name(self):
        return self._attr_name

    @property
    def state(self):
        return self._state

    async def async_update(self):
        # Placeholder: replace with real update logic
        self._state = "ok"
