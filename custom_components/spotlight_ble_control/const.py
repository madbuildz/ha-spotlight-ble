"""Public integration constants; no installation-specific device slots."""
DOMAIN = "spotlight_ble_control"
SIGNAL_UPDATED = f"{DOMAIN}_updated"
FI_LIGHT = "fi_light"
SHOWHOME = "showhome"
DEFAULT = {"on": False, "b": 128, "hs": [280, 100], "mode": "Color",
           "preset": "White 3", "effect": "Steady", "speed": 8}
