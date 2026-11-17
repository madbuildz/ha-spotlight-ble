"""Per-controller HA setup and shared, serialized Bluetooth transport."""
import asyncio
import json

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import DEFAULT, DOMAIN, FI_LIGHT, SHOWHOME, SIGNAL_UPDATED
from .protocol import (EFFECTS, FI_EFFECTS, FI_MODES, FI_UUID, PALETTES, SHOW_UUIDS,
                       fi_mode, fi_packet, show_packet)

PLATFORMS = [Platform.LIGHT, Platform.NUMBER]


async def async_setup(hass, config):
    backend = Backend(hass)
    await backend.setup()
    hass.data[DOMAIN] = backend

    async def control(call: ServiceCall):
        await backend.control(dict(call.data))

    hass.services.async_register(DOMAIN, "control", control, schema=vol.Schema({
        vol.Exclusive("entity_id", "target"): cv.entity_id,
        # Compatibility alias for migrated slots, not a list of predefined devices.
        vol.Exclusive("slot", "target"): cv.string,
        vol.Required("operation"): vol.In(["on", "off", "brightness", "color", "mode", "preset", "effect", "speed"]),
        vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional("hs"): vol.All(vol.Coerce(list), [vol.Coerce(float)], vol.Length(min=2, max=2)),
        vol.Optional("option"): cv.string,
        vol.Optional("speed"): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
        vol.Optional("preset"): vol.In(PALETTES),
        vol.Optional("effect"): vol.In(EFFECTS),
    }))
    return True


async def async_setup_entry(hass, entry):
    if entry.data.get("migration_only"):
        return True
    from .migration import async_finish_imports
    await async_finish_imports(hass, entry)
    backend = hass.data[DOMAIN]
    await backend.register(entry)
    # Move an existing entity to its migrated per-controller config entry before
    # adding the platform, preserving entity ID, area, labels and voice settings.
    registry = er.async_get(hass)
    for entity in list(registry.entities.values()):
        if (entity.platform == DOMAIN and entity.unique_id in (
                entry.data.get("entity_unique_id"),
                entry.data.get("entity_unique_id", "") + "_effect_speed")):
            if entity.config_entry_id != entry.entry_id:
                registry.async_update_entity(entity.entity_id, config_entry_id=entry.entry_id)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if entry.data.get("migration_only"):
        return True
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].devices.pop(entry.data.get("settings_key", entry.entry_id), None)
    return unloaded


async def async_migrate_entry(hass, entry):
    from .migration import async_migrate_entry as migrate
    return await migrate(hass, entry)


async def async_remove_config_entry_device(hass, entry, device):
    """Allow removal only of empty, retired devices from the old slot model."""
    from .migration import LEGACY_SLOTS
    legacy_ids = {(DOMAIN, f"{entry.entry_id}_{slot}") for slot in LEGACY_SLOTS}
    if not device.identifiers or not device.identifiers <= legacy_ids:
        return False
    for configured in hass.config_entries.async_entries(DOMAIN):
        configs = [dict(configured.data) | dict(configured.options)]
        configs.extend(configured.data.get("pending_imports", []))
        for config in configs:
            identifier = config.get("device_identifier", configured.entry_id)
            if (DOMAIN, identifier) in device.identifiers:
                return False
    if any(getattr(entity, "device_id", None) == device.id
           for entity in er.async_get(hass).entities.values()):
        return False
    return True


class Backend:
    """One transport lock and nonce store shared by any number of controllers."""
    def __init__(self, hass):
        self.hass = hass
        self.lock = asyncio.Lock()
        self.store = Store(hass, 1, DOMAIN)
        self.sequence = 13020747
        self.transaction = 14
        self.settings = {}
        self.devices = {}

    async def setup(self):
        saved = await self.store.async_load() or {}
        self.sequence = max(self.sequence, saved.get("sequence", self.sequence))
        self.transaction = saved.get("transaction", self.transaction)
        self.settings = saved.get("settings", {})

    async def register(self, entry):
        key = entry.data.get("settings_key", entry.entry_id)
        config = dict(entry.data) | dict(entry.options)
        config["entry_id"] = entry.entry_id
        self.devices[key] = config
        if key not in self.settings:
            self.settings[key] = dict(DEFAULT)
        await self.persist()

    async def persist(self):
        await self.store.async_save({"sequence": self.sequence,
                                    "transaction": self.transaction,
                                    "settings": self.settings})

    def read(self, key):
        state = DEFAULT | self.settings.get(key, {})
        state["mode"] = fi_mode(state["mode"])
        return state

    def target(self, key):
        config = self.devices[key]
        unique_id = config.get("transport_unique_id")
        registry = er.async_get(self.hass)
        if unique_id:
            # Follow entity renames and re-adds of the same Bluetooth device.
            return registry.async_get_entity_id("binary_sensor", "generic_bt", unique_id) or ""
        return config["target_entity"]

    def resolve(self, data):
        if "entity_id" in data:
            entity = er.async_get(self.hass).async_get(data["entity_id"])
            if entity and entity.platform == DOMAIN:
                for key, config in self.devices.items():
                    if config["entry_id"] == entity.config_entry_id:
                        return key
        elif data.get("slot") in self.devices:
            return data["slot"]
        raise ServiceValidationError("Select a configured Spotlight BLE entity")

    async def save(self, key, state):
        self.settings[key] = dict(state)
        await self.persist()
        # Mirror existing legacy helpers until their owners choose to remove them.
        helper = f"input_text.{key}_settings"
        if self.hass.states.get(helper) is not None:
            config = self.devices[key]
            legacy = state | {"target": self.target(key), "name": config.get("advertised_name", "")}
            value = json.dumps(legacy, separators=(",", ":"))
            if len(value) <= 255:
                await self.hass.services.async_call("input_text", "set_value", {
                    "entity_id": helper, "value": value,
                }, blocking=True)
        async_dispatcher_send(self.hass, SIGNAL_UPDATED, key)

    def validate_target(self, target):
        entity = er.async_get(self.hass).async_get(target)
        if entity is None or entity.platform != "generic_bt":
            raise ServiceValidationError("Choose a Generic Bluetooth binary_sensor entity")
        return entity

    async def control(self, data):
        async with self.lock:
            slot, operation = self.resolve(data), data["operation"]
            state = self.read(slot)
            target = self.target(slot)
            if not target:
                raise ServiceValidationError("Choose a Bluetooth target in the device integration settings")
            self.validate_target(target)
            if operation == "speed":
                if self.devices[slot]["controller_type"] == SHOWHOME:
                    raise ServiceValidationError("Trio effect speed is not verified")
                speed = data.get("speed")
                if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 1 <= speed <= 31 or int(speed) != speed:
                    raise ServiceValidationError("Effect speed must be an integer from 1 to 31")
                state["speed"] = int(speed)
                # Configuring a solid/off light must not turn it on or start an effect.
                if not state["on"] or state["mode"] not in FI_EFFECTS:
                    await self.save(slot, state)
                    return
            entity = self.hass.states.get(target)
            if entity is None or entity.state in ("unknown", "unavailable"):
                raise ServiceValidationError("The assigned Bluetooth device is unavailable")
            trio = self.devices[slot]["controller_type"] == SHOWHOME
            if trio and operation not in ("on", "preset", "effect"):
                raise ServiceValidationError("ShowHome off, dimming and arbitrary RGB are not verified; use its preset and effect controls")
            if not trio and operation in ("preset", "effect"):
                raise ServiceValidationError("Use the Floodlight mode control")
            if operation == "brightness":
                if "brightness" not in data:
                    raise ServiceValidationError("Brightness is required")
                if state["mode"] in FI_EFFECTS:
                    raise ServiceValidationError("Effect dimming is unverified; select a solid mode first")
            if (not trio and "brightness" in data
                    and operation not in ("color", "off")
                    and (fi_mode(data.get("option")) if operation == "mode" else state["mode"])
                    in FI_EFFECTS
                    and data["brightness"] != state["b"]):
                raise ServiceValidationError("Effect dimming is unverified; select a solid mode first")
            if "brightness" in data:
                state["b"] = data["brightness"]
            if operation == "color":
                if "hs" not in data:
                    raise ServiceValidationError("HS color is required")
                state.update(hs=data["hs"], mode="Color")
            if operation in ("mode", "preset", "effect"):
                option = fi_mode(data.get("option")) if operation == "mode" else data.get("option")
                allowed = {"mode": FI_MODES, "preset": PALETTES, "effect": EFFECTS}[operation]
                if option not in allowed:
                    raise ServiceValidationError(f"Invalid {operation}")
                state[operation] = option
            if trio:
                # A native Trio menu selects preset and animation atomically.
                for key, allowed in (("preset", PALETTES), ("effect", EFFECTS)):
                    if key in data:
                        if data[key] not in allowed:
                            raise ServiceValidationError(f"Invalid {key}")
                        state[key] = data[key]
            off = operation == "off" or (not trio and state["b"] == 0 and state["mode"] not in FI_EFFECTS)
            if trio:
                if self.sequence >= 0xFFFFFF:
                    raise ServiceValidationError("Mesh sequence exhausted; choose a new mesh source before continuing")
                self.sequence += 1
                self.transaction = self.transaction % 15 + 1
                # Persist before sending: failures and HA restarts must not reuse a nonce.
                await self.persist()
                packet = show_packet(self.devices[slot]["advertised_name"], self.sequence, self.transaction,
                                     state["preset"], state["effect"])
                writes = list(zip(SHOW_UUIDS, (packet[:20], packet[20:]), strict=True))
            else:
                packet = fi_packet(state, off=off)
                writes = [(FI_UUID, packet)]
            for uuid, packet in writes:
                try:
                    await self.hass.services.async_call("generic_bt", "write_gatt", {
                        "entity_id": target, "target_uuid": uuid, "data": packet.hex(),
                    }, blocking=True)
                except Exception as error:
                    raise HomeAssistantError(
                        "Bluetooth write failed. Keep the phone app closed; reload this device's Generic Bluetooth entry after the proxy reconnects. "
                        f"Details: {type(error).__name__}: {error}"
                    ) from error
            state["on"] = not off
            # Keep remembered brightness when turning off; a zero-brightness command
            # also keeps the preceding nonzero setting for the next turn-on.
            if state["b"] == 0:
                state["b"] = self.read(slot)["b"] or 128
            await self.save(slot, state)
