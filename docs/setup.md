# Setup and publishing

## Create the GitHub repository

Create a repository named `ha-spotlight-ble` under your GitHub account.
Keep it private while preparing it. HACS requires public visibility before it
can install this integration. Manual installation and authenticated ESPHome
package imports can use a private repository.

Leave **Add README**, **Add .gitignore**, and **Choose a license** unchecked/empty
when creating it: the local repository already has its initial files and commit.
This project includes an MIT license in `LICENSE`; do not generate a second license on GitHub.

Then, from this directory, use the URL GitHub gives you:

```sh
git remote add origin git@github.com:madbuildz/ha-spotlight-ble.git
git push -u origin main
```

The SSH form requires an SSH key registered with GitHub. Alternatively use:

```sh
git remote add origin https://github.com/madbuildz/ha-spotlight-ble.git
git push -u origin main
```

Use one remote URL, not both. GitHub credentials belong in your Git credential
manager, never in a committed URL or YAML file.

## Import into HA Device Builder

After publishing, use the following local device configuration. Replace
`madbuildz` with the actual GitHub owner if you are using a fork. Keep the current Wi-Fi/API/OTA values
in local `secrets.yaml`; adjust secret names to match the names you already use.

```yaml
packages:
  proxy:
    url: https://github.com/madbuildz/ha-spotlight-ble
    ref: main
    files:
      - esphome/xiao-c6-proxy.yaml
    refresh: 0s

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

api:
  encryption:
    key: !secret api_encryption_key

ota:
  - platform: esphome
    password: !secret ota_password
```

For a private repository, add `username` and `password` under the `proxy`
package, with values from local `!secret` references. The password can be a
fine-grained GitHub token with read-only Contents permission for this repository.
Do not commit the token. The public-repository form needs no GitHub credentials.

Remote package files contain no `!secret` lookups; those stay in the local wrapper.
The wrapper can override `device_name` and `friendly_name` using substitutions.

Validate in Device Builder, then choose Install and update wirelessly. Keep the
external antenna attached. A package refresh happens during configuration/build
processing; it does not change running firmware by itself. `refresh: 0s` requests
a fresh repository check each time. For repeatable releases, change `ref` to a
specific tag or commit.

The package is based on the settings verified in our tests. Preserve any useful
extra settings from the existing local configuration before replacing it. This
repository has not been compiled or flashed as part of its initial creation.

References: [packages](https://esphome.io/components/packages/),
[secrets](https://esphome.io/guides/yaml/),
[Device Builder](https://esphome.io/install/getting-started/).
