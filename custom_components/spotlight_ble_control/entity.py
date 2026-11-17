"""Shared device identity, availability and update subscriptions."""
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, SHOWHOME, SIGNAL_UPDATED


class SpotlightEntity:
    """Mixin shared by native light and speed controls on each device."""
    def __init__(self, backend, entry):
        self.backend = backend
        self.slot = entry.data.get("settings_key", entry.entry_id)
        config = backend.devices[self.slot]
        self._attr_unique_id = config.get("entity_unique_id", f"{entry.entry_id}_light")
        self._attr_name = config["name"]
        trio = config["controller_type"] == SHOWHOME
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config.get("device_identifier", entry.entry_id))},
            "name": self._attr_name,
            "manufacturer": "Holiday ShowHome compatible" if trio else "Fi Light compatible",
            "model": "Three-head BLE controller" if trio else "RGB + dual-white BLE floodlight",
        }
        self._target_unsubscribe = None

    @property
    def available(self):
        target = self.hass.states.get(self.backend.target(self.slot))
        return target is not None and target.state not in ("unknown", "unavailable")

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(
            self.hass, SIGNAL_UPDATED, self._settings_updated))
        self.async_on_remove(self._remove_target_listener)
        self._subscribe_target()

    @callback
    def _remove_target_listener(self):
        if self._target_unsubscribe:
            self._target_unsubscribe()
            self._target_unsubscribe = None

    @callback
    def _subscribe_target(self):
        self._remove_target_listener()
        target = self.backend.target(self.slot)
        if target:
            self._target_unsubscribe = async_track_state_change_event(
                self.hass, [target], self._target_updated)

    @callback
    def _target_updated(self, event):
        self._subscribe_target()
        self.async_write_ha_state()

    @callback
    def _settings_updated(self, slot):
        if slot == self.slot:
            self._subscribe_target()
            self.async_write_ha_state()

