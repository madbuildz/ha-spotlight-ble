"""Upgrade the former six-slot backend without resetting settings or nonces."""
import json
from homeassistant import config_entries
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, FI_LIGHT, SHOWHOME

# Only the migration knows the old slot names. New installations never create them.
LEGACY_SLOTS = [f"floodlight_{n}" for n in range(1, 5)] + [f"spotlight_trio_{n}" for n in range(1, 3)]


async def async_migrate_entry(hass, entry):
    if entry.version > 2:
        return False
    if entry.version == 2:
        return True
    backend = hass.data[DOMAIN]
    registry = er.async_get(hass)
    assigned = []
    identities = set()
    for slot in LEGACY_SLOTS:
        saved = backend.settings.get(slot)
        if saved is None:
            helper = hass.states.get(f"input_text.{slot}_settings")
            try:
                saved = json.loads(helper.state) if helper else {}
            except (ValueError, TypeError):
                saved = {}
        if not isinstance(saved, dict) or not saved.get("target"):
            continue
        target = registry.async_get(saved["target"])
        unique_id = str(target.unique_id) if target else saved["target"]
        if unique_id.casefold() in identities:
            continue
        identities.add(unique_id.casefold())
        old_unique = f"{entry.entry_id}_{slot}"
        old_entity_id = registry.async_get_entity_id("light", DOMAIN, old_unique)
        old_entity = registry.async_get(old_entity_id) if old_entity_id else None
        name = (old_entity.name or old_entity.original_name) if old_entity else None
        config = {
            "controller_type": SHOWHOME if slot.startswith("spotlight_trio") else FI_LIGHT,
            "name": name or slot.replace("_", " ").title(),
            "target_entity": saved["target"], "transport_unique_id": unique_id,
            "advertised_name": saved.get("name", ""),
            "settings_key": slot, "entity_unique_id": old_unique,
            "device_identifier": old_unique,
        }
        backend.settings[slot] = saved
        assigned.append(config)
    await backend.persist()

    # Unassigned old entities are retired, rather than recreated as unavailable
    # devices. Their records stay disabled/hidden as an upgrade rollback option.
    active = {item["entity_unique_id"] for item in assigned}
    for entity in list(registry.entities.values()):
        if entity.config_entry_id == entry.entry_id and entity.platform == DOMAIN:
            if entity.unique_id not in active and not any(entity.unique_id == key + "_effect_speed" for key in active):
                registry.async_update_entity(entity.entity_id,
                    disabled_by=entity.disabled_by or er.RegistryEntryDisabler.INTEGRATION,
                    hidden_by=entity.hidden_by or er.RegistryEntryHider.INTEGRATION)
    if assigned:
        first, *remaining = assigned
        if remaining:
            first["pending_imports"] = remaining
        hass.config_entries.async_update_entry(entry, version=2, title=first["name"],
            unique_id=first["transport_unique_id"].casefold(), data=first)
        await async_finish_imports(hass, entry)
    else:
        # Nothing was assigned: keep only an inert upgrade marker. New devices
        # are added through the normal UI; no placeholder controls are created.
        hass.config_entries.async_update_entry(entry, version=2,
            title="Legacy migration (no configured devices)", data={"migration_only": True})
    return True


async def async_finish_imports(hass, entry):
    """Idempotently resume additional-device migration after an interrupted boot."""
    pending = entry.data.get("pending_imports", [])
    if not pending:
        return
    for config in pending:
        result = await hass.config_entries.flow.async_init(DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT}, data=config)
        if result.get("type") != "create_entry" and not (
                result.get("type") == "abort" and result.get("reason") == "already_configured"):
            raise ConfigEntryNotReady("Additional spotlight device migration must be retried")
    data = dict(entry.data)
    data.pop("pending_imports", None)
    hass.config_entries.async_update_entry(entry, data=data)
