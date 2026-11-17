# Per-device configuration and migration

There is one HA configuration entry per physical controller. Adding another
controller runs the Add integration flow again; no source edit is necessary.
Fi Light creates one light and one speed number. ShowHome creates one light for
its whole three-head controller. HACS installs the classes, not user entities.

The configuration flow stores controller type, friendly name and Bluetooth target
in HA. Generic Bluetooth’s unique ID identifies that target across entity renames.
Configure changes the local mapping; it never sends a command to the light.
Settings are keyed by config-entry ID and stored by HA’s storage API. ShowHome’s
packet sequence/transaction store and transport lock are shared across entries,
so parallel controllers do not reuse mesh nonces. No `.storage` files are edited
directly, and no actual addresses belong in the repository.

## Legacy upgrade

The former singleton entry is converted into its first assigned controller.
Other assigned slots become additional entries; empty slots create nothing.
The migration retains each assigned light’s original unique ID and settings key,
so its entity ID, labels, areas, voice settings and remembered color remain.
Additional entries claim the corresponding old registry entities through HA’s
registry API before their platforms load. Nonce counters are never reset.
If migration is interrupted, pending additional-device imports resume idempotently
on the next setup; duplicate Bluetooth entries are not created.

Unassigned old registry entities are disabled and hidden, not recreated. Their
records remain solely for upgrade rollback. Old template helpers or scripts are
not deleted automatically; disable them after checking references. They are not
needed for current native controls. A migration with no assigned devices retains
an inert marker entry. Add actual devices normally; the marker has no controls.

Make an HA backup before applying the architecture upgrade if you need a full
rollback: old releases do not understand the new config-entry schema. The existing
fixed-slot JSON remains in the managed state store to preserve migration history;
new installations never initialize those keys.

## Advanced actions

Normal use is `light.turn_on`, `light.turn_off` (Fi Light only), and
`number.set_value` on the speed slider. The compatibility action accepts a native
light entity instead of a fixed slot:

```yaml
action: spotlight_ble_control.control
data:
  entity_id: light.example_floodlight
  operation: speed
  speed: 16
```

Old actions using a migrated `slot` still resolve to that controller. They cannot
create devices. The old Assign action is replaced by the per-device setup and
Configure forms.
