"""Fi Light effect-speed controls, grouped with their native lights."""
from homeassistant.components.number import NumberEntity, NumberMode

from .const import DOMAIN, FI_LIGHT
from .entity import SpotlightEntity


async def async_setup_entry(hass, entry, async_add_entities):
    backend = hass.data[DOMAIN]
    if entry.data.get("controller_type") == FI_LIGHT:
        async_add_entities([EffectSpeed(backend, entry)])


class EffectSpeed(SpotlightEntity, NumberEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_native_min_value = 1
    _attr_native_max_value = 31
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:speedometer"

    def __init__(self, backend, entry):
        super().__init__(backend, entry)
        self._attr_unique_id += "_effect_speed"
        self._attr_name = "Effect speed"

    @property
    def native_value(self):
        return self.backend.read(self.slot)["speed"]

    async def async_set_native_value(self, value):
        await self.backend.control({"slot": self.slot, "operation": "speed", "speed": value})
