# Home Assistant scripts

`showhome_send_packet.yaml` is a script configuration body, not a complete
`scripts.yaml` file. Create a script in HA's UI, switch to its YAML editor, paste
the body, and save. It requires the existing Generic Bluetooth integration.
This repository creation does not install or change anything in HA.

Provide the target Generic Bluetooth binary sensor plus the low/high hex chunks
of a freshly generated encrypted CSRmesh packet. The condition rejects missing,
malformed, or unavailable inputs. `queued` mode keeps calls to this helper from
interleaving their packet chunks. Avoid other scripts writing to the same
controller concurrently.

This helper does not encode colors, generate encryption, discover changing BLE
addresses, fix the integration's cached connections, or confirm the visible
color. Reusing identical encrypted packets can be ignored by the controller.
The packet-generation workflow remains separate; captured packets are not
included as reusable controls. See `../../docs/spotlight-protocol.md`.
