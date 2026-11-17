"""Native Fi Light entities: one panel for color, brightness, whites and effects."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_EFFECT, ATTR_HS_COLOR, ATTR_WHITE,
    ColorMode, LightEntity, LightEntityFeature,
)
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN, FI_LIGHT
from .entity import SpotlightEntity
from .protocol import EFFECTS, PALETTES, FI_EFFECTS, FI_MODES, fi_mode


async def async_setup_entry(hass, entry, async_add_entities):
    backend = hass.data[DOMAIN]
    if entry.data.get("migration_only"):
        return
    entity_class = Floodlight if entry.data["controller_type"] == FI_LIGHT else SpotlightTrio
    async_add_entities([entity_class(backend, entry)])


class Floodlight(SpotlightEntity, LightEntity):
    """Report the last successfully written command, not physical state readback."""
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_supported_color_modes = {ColorMode.HS, ColorMode.WHITE}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = FI_MODES

    @property
    def is_on(self):
        return self.backend.read(self.slot)["on"]

    @property
    def brightness(self):
        return self.backend.read(self.slot)["b"]

    @property
    def color_mode(self):
        if self.effect in FI_EFFECTS:
            return ColorMode.ONOFF
        return ColorMode.HS if self.effect == "Color" else ColorMode.WHITE

    @property
    def hs_color(self):
        return tuple(self.backend.read(self.slot)["hs"]) if self.effect == "Color" else None

    @property
    def effect(self):
        return self.backend.read(self.slot)["mode"]

    async def async_turn_on(self, **kwargs):
        """Send color/brightness or mode/brightness in one BLE write."""
        data = {"slot": self.slot, "operation": "on"}
        if ATTR_HS_COLOR in kwargs:
            if ATTR_EFFECT in kwargs and fi_mode(kwargs[ATTR_EFFECT]) != "Color":
                raise ServiceValidationError("Choose either RGB color or an effect")
            data.update(operation="color", hs=list(kwargs[ATTR_HS_COLOR]))
        elif ATTR_EFFECT in kwargs:
            data.update(operation="mode", option=kwargs[ATTR_EFFECT])
        elif ATTR_WHITE in kwargs:
            data.update(operation="mode", option="Both white channels")
        if ATTR_BRIGHTNESS in kwargs:
            data["brightness"] = kwargs[ATTR_BRIGHTNESS]
        if ATTR_WHITE in kwargs:
            data["brightness"] = kwargs[ATTR_WHITE]
        await self.backend.control(data)

    async def async_turn_off(self, **kwargs):
        await self.backend.control({"slot": self.slot, "operation": "off"})


TRIO_EFFECTS = {f"{preset} · {effect}": (preset, effect)
                for effect in EFFECTS for preset in PALETTES}


class SpotlightTrio(SpotlightEntity, LightEntity):
    """One controller entity with atomic preset/animation combinations."""
    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = list(TRIO_EFFECTS)
    _attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self):
        return self.backend.read(self.slot)["on"]

    @property
    def effect(self):
        state = self.backend.read(self.slot)
        return f"{state['preset']} · {state['effect']}"

    @property
    def extra_state_attributes(self):
        state = self.backend.read(self.slot)
        return {"preset": state["preset"], "animation": state["effect"]}

    async def async_turn_on(self, **kwargs):
        data = {"slot": self.slot, "operation": "on"}
        if ATTR_EFFECT in kwargs:
            try:
                preset, effect = TRIO_EFFECTS[kwargs[ATTR_EFFECT]]
            except KeyError:
                raise ServiceValidationError("Choose a Trio preset and animation from the Effects menu") from None
            data.update(preset=preset, effect=effect)
        await self.backend.control(data)

    async def async_turn_off(self, **kwargs):
        raise ServiceValidationError("ShowHome off is not verified; use the light's preset/effect controls")
