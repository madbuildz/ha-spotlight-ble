"""Build reviewable YAML exports from the UI helper definitions."""
import json
from pathlib import Path
import yaml

root = Path(__file__).parent
definitions = json.loads((root / "config/definitions.json").read_text())
selectors = json.loads((root / "config/selectors.json").read_text())
package = {"input_text": {}, "script": definitions["scripts"], "template": [{"light": [], "select": []}]}
for slot in definitions["slots"]:
    package["input_text"][slot["slot"] + "_settings"] = {"name": slot["name"] + " settings", "max": 255}
    config = dict(slot["light"])
    config["availability"] = config.pop("additional_options")["availability"]
    config["unique_id"] = "spotlight_ble_" + slot["slot"]
    package["template"][0]["light"].append(config)
for index, selector in enumerate(selectors):
    config = dict(selector["config"])
    config["availability"] = config.pop("additional_options")["availability"]
    config["unique_id"] = "spotlight_ble_select_" + str(index + 1)
    package["template"][0]["select"].append(config)
(root / "spotlights.package.yaml").write_text(
    "# Alternative for a NEW installation. Do not import alongside the UI-created helpers.\n"
    "# Settings have no initial value, so HA restores assignments across restarts.\n"
    + yaml.safe_dump(package, sort_keys=False, allow_unicode=True)
)
for name, config in definitions["scripts"].items():
    (root / "config" / (name + ".yaml")).write_text(yaml.safe_dump(config, sort_keys=False))
