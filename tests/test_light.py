"""Per-device setup, transport, migration and native-control tests.

HA boundary doubles keep these tests independent of HA's Python runtime. Live
HA checks additionally exercise the real config flow and platform schemas.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

Cipher(algorithms.AES(bytes(16)), modes.ECB()).encryptor()
ROOT = Path(__file__).resolve().parents[1] / 'custom_components/spotlight_ble_control'


def module(name, **attrs):
    obj = ModuleType(name)
    obj.__dict__.update(attrs)
    return obj


class HAError(Exception):
    pass


class MemoryStore:
    def __init__(self, *args):
        self.saved = {}
    async def async_load(self):
        return copy.deepcopy(self.saved)
    async def async_save(self, value):
        self.saved = copy.deepcopy(value)


class Flow:
    def __init_subclass__(cls, **kwargs):
        pass
    async def async_set_unique_id(self, value):
        self.unique_id = value
    def _abort_if_unique_id_configured(self):
        pass
    def async_create_entry(self, **kwargs):
        return {'type': 'create_entry'} | kwargs
    def async_show_form(self, **kwargs):
        return {'type': 'form'} | kwargs


def load_modules():
    mods = {
        'voluptuous': module('voluptuous', Schema=lambda value: value, Required=lambda key, **kw: key, Optional=lambda key, **kw: key),
        'homeassistant': module('homeassistant'),
        'homeassistant.config_entries': module('config_entries', ConfigFlow=Flow, OptionsFlow=Flow, SOURCE_IMPORT='import'),
        'homeassistant.const': module('const', Platform=NS(LIGHT='light', NUMBER='number')),
        'homeassistant.core': module('core', ServiceCall=object, callback=lambda f: f),
        'homeassistant.exceptions': module('exceptions', HomeAssistantError=HAError, ServiceValidationError=HAError, ConfigEntryNotReady=HAError),
        'homeassistant.helpers': module('helpers'),
        'homeassistant.helpers.storage': module('storage', Store=MemoryStore),
        'homeassistant.helpers.dispatcher': module('dispatcher', async_dispatcher_send=lambda *a: None, async_dispatcher_connect=lambda *a: lambda: None),
        'homeassistant.helpers.event': module('event', async_track_state_change_event=lambda *a: lambda: None),
        'homeassistant.helpers.config_validation': module('cv', string=str),
        'homeassistant.helpers.entity_registry': module('er', async_get=lambda hass: hass.registry, RegistryEntryDisabler=NS(INTEGRATION='integration'), RegistryEntryHider=NS(INTEGRATION='integration')),
        'homeassistant.helpers.selector': module('selector', SelectSelector=lambda value: value, EntitySelector=lambda value: value),
        'homeassistant.components': module('components'),
        'homeassistant.components.number': module('number', NumberEntity=object, NumberMode=NS(SLIDER='slider')),
        'homeassistant.components.light': module('light', ATTR_BRIGHTNESS='brightness', ATTR_EFFECT='effect', ATTR_HS_COLOR='hs_color', ATTR_WHITE='white', ColorMode=NS(HS='hs', WHITE='white', ONOFF='onoff'), LightEntity=object, LightEntityFeature=NS(EFFECT=4)),
    }
    for name, value in mods.items():
        value.__name__, value.__path__ = name, []
    with patch.dict(sys.modules, mods):
        spec = importlib.util.spec_from_file_location('spotlight_test', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
        backend = importlib.util.module_from_spec(spec)
        sys.modules['spotlight_test'] = backend
        spec.loader.exec_module(backend)
        loaded = [backend]
        for name in ('light', 'number', 'config_flow', 'migration'):
            spec = importlib.util.spec_from_file_location('spotlight_test.' + name, ROOT / (name + '.py'))
            obj = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(obj)
            loaded.append(obj)
    return loaded


b, light, number, flow, migration = load_modules()


class Registry:
    def __init__(self):
        self.entities = {}
    def add(self, entity_id, platform, unique_id, **kwargs):
        self.entities[entity_id] = NS(entity_id=entity_id, platform=platform, unique_id=unique_id,
            config_entry_id=kwargs.pop('config_entry_id', None), disabled_by=None,
            hidden_by=None, name=None, original_name=None, **kwargs)
    def async_get(self, entity_id):
        return self.entities.get(entity_id)
    def async_get_entity_id(self, domain, platform, unique_id):
        return next((e.entity_id for e in self.entities.values() if e.entity_id.startswith(domain+'.') and e.platform == platform and e.unique_id == unique_id), None)
    def async_update_entity(self, entity_id, **changes):
        e = self.entities[entity_id]
        for key, value in changes.items():
            setattr(e, key, value)
        return e


def entry(key, controller_type='fi_light', **changes):
    config = {'controller_type': controller_type, 'name': 'Example light',
        'target_entity': 'binary_sensor.example', 'transport_unique_id': '02:00:00:00:00:01',
        'advertised_name': 'LA2000034C3D4' if controller_type == 'showhome' else ''} | changes
    return NS(entry_id=key, data=config, options={}, version=2, title=config['name'], unique_id=config['transport_unique_id'].casefold())


class NativeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.states = {'binary_sensor.example': NS(state='on')}
        registry = Registry()
        registry.add('binary_sensor.example', 'generic_bt', '02:00:00:00:00:01')
        self.entries = []
        def update_entry(e, **changes):
            for key, value in changes.items():
                setattr(e, key, value)
        config_entries = NS(async_entries=lambda domain: self.entries, async_update_entry=update_entry,
            flow=NS(async_init=AsyncMock(return_value={"type": "create_entry"})))
        self.hass = NS(states=NS(get=self.states.get), registry=registry,
            services=NS(async_call=AsyncMock()), config_entries=config_entries, data={})
        self.backend = b.Backend(self.hass)
        await self.backend.setup()
        self.hass.data[b.DOMAIN] = self.backend
        self.config = entry('device-one')
        self.entries.append(self.config)
        await self.backend.register(self.config)
        self.entity = light.Floodlight(self.backend, self.config)
        self.entity.hass = self.hass

    @patch.dict(sys.modules, {"spotlight_test.migration": migration})
    async def test_only_empty_retired_legacy_devices_can_be_removed(self):
        self.config.data['device_identifier'] = 'device-one_floodlight_1'
        device = NS(id='old-device', identifiers={(b.DOMAIN, 'device-one_floodlight_2')})
        self.assertTrue(await b.async_remove_config_entry_device(self.hass, self.config, device))
        device.identifiers = {(b.DOMAIN, 'device-one_floodlight_1')}
        self.assertFalse(await b.async_remove_config_entry_device(self.hass, self.config, device))
        device.identifiers = {(b.DOMAIN, 'device-one_floodlight_2')}
        self.hass.registry.add('light.retired', b.DOMAIN, 'retired', device_id=device.id)
        self.assertFalse(await b.async_remove_config_entry_device(self.hass, self.config, device))
        self.hass.registry.entities.pop('light.retired')
        device.identifiers = {(b.DOMAIN, 'unrelated')}
        self.assertFalse(await b.async_remove_config_entry_device(self.hass, self.config, device))

    def packet(self):
        return self.hass.services.async_call.call_args.args[2]['data']

    async def test_fresh_install_creates_no_slots_and_arbitrary_device_count(self):
        fresh = b.Backend(self.hass)
        await fresh.setup()
        self.assertEqual(fresh.settings, {})
        self.assertEqual(fresh.devices, {})
        for n in range(12):
            e = entry(f'controller-{n}')
            await fresh.register(e)
        self.assertEqual(len(fresh.devices), 12)
        self.assertNotIn('floodlight_1', fresh.devices)

    async def test_platforms_create_only_the_configured_controller(self):
        entities = []
        await light.async_setup_entry(self.hass, self.config, lambda values: entities.extend(values))
        await number.async_setup_entry(self.hass, self.config, lambda values: entities.extend(values))
        self.assertEqual(len(entities), 2)
        trio_entry = entry('a-trio', 'showhome')
        await self.backend.register(trio_entry)
        entities.clear()
        await light.async_setup_entry(self.hass, trio_entry, lambda values: entities.extend(values))
        await number.async_setup_entry(self.hass, trio_entry, lambda values: entities.extend(values))
        self.assertEqual(len(entities), 1)
        self.assertIsInstance(entities[0], light.SpotlightTrio)

    async def test_color_picker_tuple_and_brightness_make_one_packet(self):
        await self.entity.async_turn_on(hs_color=(240, 100), brightness=128)
        self.hass.services.async_call.assert_awaited_once()
        self.assertEqual(self.packet(), '28000080000000f029')
        self.assertEqual(self.entity.hs_color, (240, 100))

    async def test_white_modes_and_return_to_rgb(self):
        for effect, packet in [('White channel 1', '280000008000000f29'), ('White channel 2', '280000000080000f29'), ('Both white channels', '280000008080000f29')]:
            await self.entity.async_turn_on(effect=effect, brightness=128)
            self.assertEqual(self.packet(), packet)
            self.assertEqual(self.entity.color_mode, 'white')
        await self.entity.async_turn_on(hs_color=(0, 100))
        self.assertEqual(self.packet(), '28800000000000f029')

    async def test_effect_off_restore_and_remembered_rgb(self):
        await self.entity.async_turn_on(hs_color=(240, 100), brightness=100)
        await self.entity.async_turn_on(effect='Pulse purple')
        self.assertEqual(self.packet(), 'fd2b18fc')
        self.assertEqual(self.entity.color_mode, 'onoff')
        await self.entity.async_turn_off()
        self.assertEqual(self.packet(), '28000000000000f029')
        await self.entity.async_turn_on()
        self.assertEqual(self.packet(), 'fd2b18fc')
        await self.entity.async_turn_on(effect='Color')
        self.assertEqual(self.packet(), '28000064000000f029')

    async def test_all_effects_reject_unverified_dimming(self):
        for mode in b.FI_EFFECTS:
            await self.entity.async_turn_on(effect=mode)
            before = self.backend.read('device-one')
            with self.assertRaises(HAError):
                await self.entity.async_turn_on(brightness=20)
            self.assertEqual(self.backend.read('device-one'), before)

    async def test_write_failure_does_not_publish_requested_color(self):
        before = self.backend.read('device-one')
        self.hass.services.async_call.side_effect = RuntimeError('Disconnected')
        with self.assertRaises(HAError):
            await self.entity.async_turn_on(hs_color=(0, 100))
        self.assertEqual(self.backend.read('device-one'), before)

    async def test_transport_rename_and_missing_device(self):
        target = self.hass.registry.entities.pop('binary_sensor.example')
        target.entity_id = 'binary_sensor.renamed'
        self.hass.registry.entities[target.entity_id] = target
        self.states[target.entity_id] = self.states.pop('binary_sensor.example')
        self.assertEqual(self.backend.target('device-one'), target.entity_id)
        await self.entity.async_turn_on()
        self.assertEqual(self.hass.services.async_call.call_args.args[2]['entity_id'], target.entity_id)
        self.hass.registry.entities.clear()
        self.assertFalse(self.entity.available)
        with self.assertRaises(HAError):
            await self.entity.async_turn_on()

    async def test_speed_updates_effect_and_remembers_without_turning_on(self):
        speed = number.EffectSpeed(self.backend, self.config)
        await speed.async_set_native_value(31)
        self.hass.services.async_call.assert_not_awaited()
        self.assertFalse(self.entity.is_on)
        await self.entity.async_turn_on(effect='Pulse purple')
        self.assertEqual(self.packet(), 'fd2b01fc')
        await speed.async_set_native_value(1)
        self.assertEqual(self.packet(), 'fd2b1ffc')
        self.assertEqual(self.entity.effect, 'Pulse purple')
        await self.entity.async_turn_off()
        self.hass.services.async_call.reset_mock()
        await speed.async_set_native_value(16)
        self.hass.services.async_call.assert_not_awaited()
        self.assertFalse(self.entity.is_on)
        for bad in (0, 32, 1.5, True, None):
            with self.assertRaises(HAError):
                await speed.async_set_native_value(bad)

    async def test_speed_and_settings_survive_restart_and_are_independent(self):
        await self.backend.register(entry('another-device'))
        await self.backend.control({'slot': 'device-one', 'operation': 'speed', 'speed': 20})
        restarted = b.Backend(self.hass)
        restarted.store.saved = copy.deepcopy(self.backend.store.saved)
        await restarted.setup()
        self.assertEqual(restarted.read('device-one')['speed'], 20)
        self.assertEqual(restarted.read('another-device')['speed'], 8)

    async def test_trio_atomic_packet_and_nonce_saved_before_writes(self):
        config = entry('any-trio-name', 'showhome')
        await self.backend.register(config)
        trio = light.SpotlightTrio(self.backend, config)
        previous = self.backend.sequence
        async def reserved(*args, **kwargs):
            self.assertGreater(self.backend.store.saved['sequence'], previous)
        self.hass.services.async_call.side_effect = reserved
        await trio.async_turn_on(effect='Christmas · Blink')
        writes = self.hass.services.async_call.await_args_list
        self.assertEqual(len(writes), 2)
        packet = ''.join(c.args[2]['data'] for c in writes)
        self.assertEqual(packet, b.show_packet('LA2000034C3D4', self.backend.sequence, self.backend.transaction, 'Christmas', 'Blink').hex())
        self.assertEqual(trio.effect, 'Christmas · Blink')
        self.assertEqual(len(light.TRIO_EFFECTS), 290)
        with self.assertRaises(HAError):
            await trio.async_turn_off()

    async def test_user_flow_validates_and_prevents_duplicates(self):
        config = {'controller_type': 'fi_light', 'name': 'My porch', 'target_entity': 'binary_sensor.example'}
        f = flow.SpotlightFlow(); f.hass = self.hass
        result = await f.async_step_user(config)
        self.assertEqual(result['errors']['target_entity'], 'already_configured')
        self.entries.clear()
        result = await f.async_step_user(config)
        self.assertEqual(result['type'], 'create_entry')
        self.assertEqual(result['title'], 'My porch')
        self.assertEqual(result['data']['transport_unique_id'], '02:00:00:00:00:01')
        self.assertNotIn('settings_key', result['data'])
        self.assertFalse(self.hass.services.async_call.called)
        clean, errors = flow.validate_input(self.hass, config | {'controller_type': 'showhome', 'advertised_name': 'bad'})
        self.assertIn('advertised_name', errors)

    async def test_migration_preserves_assigned_identity_counters_and_retires_empty_slots(self):
        old = NS(entry_id='old-hub', version=1, data={}, options={}, title='Spotlight BLE', unique_id=b.DOMAIN)
        self.backend.settings = {'floodlight_1': {'target': 'binary_sensor.example', 'name': '', 'b': 42, 'hs': [300, 90], 'on': True},
                                 'floodlight_2': {'target': ''}}
        self.backend.sequence = 15000001
        self.hass.registry.add('light.my_porch', b.DOMAIN, 'old-hub_floodlight_1', config_entry_id='old-hub')
        self.hass.registry.add('light.empty_slot', b.DOMAIN, 'old-hub_floodlight_2', config_entry_id='old-hub')
        self.assertTrue(await migration.async_migrate_entry(self.hass, old))
        self.assertEqual(old.version, 2)
        self.assertEqual(old.data['settings_key'], 'floodlight_1')
        self.assertEqual(old.data['entity_unique_id'], 'old-hub_floodlight_1')
        self.assertEqual(self.backend.store.saved['sequence'], 15000001)
        self.assertEqual(self.backend.read('floodlight_1')['b'], 42)
        self.assertEqual(self.hass.registry.entities['light.empty_slot'].disabled_by, 'integration')
        self.assertIsNone(self.hass.registry.entities['light.my_porch'].disabled_by)
        self.hass.config_entries.flow.async_init.assert_not_awaited()

    async def test_migration_creates_additional_entries_only_for_assigned_devices(self):
        old = NS(entry_id='old-hub', version=1, data={}, options={}, title='Spotlight BLE', unique_id=b.DOMAIN)
        self.hass.registry.add('binary_sensor.second', 'generic_bt', '02:00:00:00:00:02')
        self.backend.settings = {'floodlight_1': {'target': 'binary_sensor.example'},
            'spotlight_trio_1': {'target': 'binary_sensor.second', 'name': 'LA2000034C3D4'}}
        await migration.async_migrate_entry(self.hass, old)
        call = self.hass.config_entries.flow.async_init.await_args
        self.assertEqual(call.kwargs['data']['controller_type'], 'showhome')
        self.assertEqual(call.kwargs['data']['settings_key'], 'spotlight_trio_1')
        self.hass.config_entries.flow.async_init.assert_awaited_once()

    async def test_options_edit_mapping_without_writing_light(self):
        options = flow.SpotlightOptionsFlow()
        options.hass, options.config_entry = self.hass, self.config
        result = await options.async_step_init({'name': 'Renamed porch', 'target_entity': 'binary_sensor.example', 'advertised_name': ''})
        self.assertEqual(result['type'], 'create_entry')
        self.assertEqual(result['data']['name'], 'Renamed porch')
        self.assertEqual(self.config.title, 'Renamed porch')
        self.hass.services.async_call.assert_not_awaited()

    async def test_interrupted_additional_migration_is_resumable(self):
        old = NS(entry_id='old-hub', version=1, data={}, options={}, title='Spotlight BLE', unique_id=b.DOMAIN)
        self.hass.registry.add('binary_sensor.second', 'generic_bt', '02:00:00:00:00:02')
        self.backend.settings = {'floodlight_1': {'target': 'binary_sensor.example'},
            'spotlight_trio_1': {'target': 'binary_sensor.second', 'name': 'LA2000034C3D4'}}
        self.hass.config_entries.flow.async_init.return_value = {'type': 'abort', 'reason': 'temporary_failure'}
        with self.assertRaises(HAError):
            await migration.async_migrate_entry(self.hass, old)
        self.assertEqual(old.version, 2)
        self.assertEqual(len(old.data['pending_imports']), 1)
        self.hass.config_entries.flow.async_init.return_value = {'type': 'abort', 'reason': 'already_configured'}
        await migration.async_finish_imports(self.hass, old)
        self.assertNotIn('pending_imports', old.data)

    async def test_empty_legacy_install_has_no_placeholder_devices(self):
        old = NS(entry_id='old-hub', version=1, data={}, options={}, title='Spotlight BLE', unique_id=b.DOMAIN)
        await migration.async_migrate_entry(self.hass, old)
        self.assertEqual(old.data, {'migration_only': True})
        self.hass.config_entries.flow.async_init.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
