"""Add one physical controller per config entry, with editable local settings."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector

from .const import DOMAIN, FI_LIGHT, SHOWHOME
from .protocol import show_identity


def device_schema(current=None, *, options=False):
    current = current or {}
    fields = {}
    if not options:
        fields[vol.Required("controller_type", default=current.get("controller_type", FI_LIGHT))] = selector.SelectSelector({
            "options": [{"value": FI_LIGHT, "label": "Fi Light floodlight"},
                        {"value": SHOWHOME, "label": "Holiday ShowHome three-head controller"}],
            "mode": "dropdown",
        })
    fields[vol.Required("name", default=current.get("name", "Spotlight"))] = str
    fields[vol.Required("target_entity", default=current.get("target_entity", ""))] = selector.EntitySelector({
        "filter": {"domain": "binary_sensor", "integration": "generic_bt"},
    })
    fields[vol.Optional("advertised_name", default=current.get("advertised_name", ""))] = str
    return vol.Schema(fields)


def validate_input(hass, data, *, exclude_entry_id=None):
    """Validate without connecting to or writing the physical light."""
    clean = dict(data)
    errors = {}
    clean["name"] = data["name"].strip()
    clean["advertised_name"] = data.get("advertised_name", "").strip()
    if not clean["name"]:
        errors["name"] = "name_required"
    registry = er.async_get(hass)
    target = registry.async_get(data["target_entity"])
    if target is None or target.platform != "generic_bt" or not target.entity_id.startswith("binary_sensor."):
        errors["target_entity"] = "invalid_target"
    else:
        clean["transport_unique_id"] = str(target.unique_id)
        identity = str(target.unique_id).casefold()
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id != exclude_entry_id and entry.unique_id == identity:
                errors["target_entity"] = "already_configured"
    if data["controller_type"] == SHOWHOME:
        try:
            show_identity(clean["advertised_name"])
        except ValueError:
            errors["advertised_name"] = "invalid_advertised_name"
    elif data["controller_type"] != FI_LIGHT:
        errors["controller_type"] = "invalid_type"
    return clean, errors


class SpotlightFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            clean, errors = validate_input(self.hass, user_input)
            if not errors:
                await self.async_set_unique_id(clean["transport_unique_id"].casefold())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=clean["name"], data=clean)
        return self.async_show_form(step_id="user", data_schema=device_schema(user_input), errors=errors)

    async def async_step_import(self, user_input):
        """Create additional per-controller entries during a legacy migration."""
        await self.async_set_unique_id(user_input["transport_unique_id"].casefold())
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=user_input["name"], data=user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SpotlightOptionsFlow()


class SpotlightOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if self.config_entry.data.get("migration_only"):
            return self.async_abort(reason="no_device")
        current = dict(self.config_entry.data) | dict(self.config_entry.options)
        if current.get("transport_unique_id"):
            current["target_entity"] = er.async_get(self.hass).async_get_entity_id(
                "binary_sensor", "generic_bt", current["transport_unique_id"]) or current["target_entity"]
        errors = {}
        if user_input is not None:
            clean, errors = validate_input(self.hass, current | user_input,
                                           exclude_entry_id=self.config_entry.entry_id)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, title=clean["name"],
                    unique_id=clean["transport_unique_id"].casefold())
                return self.async_create_entry(title="", data=clean)
        return self.async_show_form(step_id="init", data_schema=device_schema(current | (user_input or {}), options=True), errors=errors)
