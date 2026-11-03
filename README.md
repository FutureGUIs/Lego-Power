# LEGO Power

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/ajachierno/Lego-Power/actions/workflows/validate.yml/badge.svg)](https://github.com/ajachierno/Lego-Power/actions/workflows/validate.yml)

A Home Assistant integration that controls **LEGO® Powered Up** motors directly
over Bluetooth Low Energy, using the
[LEGO Wireless Protocol v3](https://lego.github.io/lego-ble-wireless-protocol-docs/).

Each LEGO hub becomes a proper Home Assistant **device** with controllable
entities, so you can run and stop motors from the UI, dashboards, scripts and
automations — no helper scripts or button presses required. The integration
supports **multiple hubs**, each added as its own device.

> LEGO® is a trademark of the LEGO Group, which does not sponsor, authorise or
> endorse this project.

> [!WARNING]
> **Tested only on the LEGO® Piano (21323).** Other Powered Up hubs and motors
> should work, but are unverified. **Do not run the piano motor at full speed —
> the gears will skip.** The default speed is a safe **50 %**; raise it carefully.

## Features

- 🎛️ **Motor switch** — turn on to run the motor, off to stop it.
- 🔌 **Connection switch** — connect or disconnect the hub from Home Assistant.
- 🏎️ **Speed control** — a live slider (1–100%); defaults to a gear-safe 50%.
- 📶 **Connected** binary sensor — shows the live Bluetooth connection status.
- ➕ **Multiple devices** — add as many hubs as you like, one config entry each.
- 🔁 **Auto‑reconnect** — re‑establishes the link when the hub comes back in range.
- 🎚️ **Live device controls** — motor port, direction (Reverse toggle) and
  stop behaviour (Brake toggle) are adjustable right on the device page, no
  reconfigure dialog needed.

## How it works

LEGO Powered Up hubs (City Hub 88009, Technic Hub 88012, Boost Move Hub 88006,
etc.) expose a single BLE service (`00001623-…`) with one characteristic
(`00001624-…`). This integration sends *Port Output Commands*
(`WriteDirectModeData`, direct power mode) to start and stop the motor on the
configured port.

Home Assistant's Bluetooth stack provides the radio. If your Home Assistant host
has no Bluetooth, or the hub is out of range, an
[ESPHome Bluetooth Proxy](https://esphome.io/projects/?type=bluetooth) (such as
an ESP32) will transparently relay the connection — no extra configuration in
this integration is needed.

## Requirements

- Home Assistant **2026.3.0** or newer.
- The [Bluetooth integration](https://www.home-assistant.io/integrations/bluetooth/)
  configured (a local adapter or an ESPHome Bluetooth proxy in range of the hub).

## Installation

### HACS (recommended)

1. In HACS, search for **LEGO Power**.
2. Open it, select **Download**, and restart Home Assistant.

### Manual

Copy `custom_components/lego_power` into your Home Assistant `config/custom_components`
directory and restart.

## Setup

A powered‑on hub in range is usually **discovered automatically** — look for a
"LEGO Power" notification under *Settings → Devices & Services*.

To add one manually: **Settings → Devices & Services → Add Integration →
LEGO Power**, pick the hub, then set:

| Option | Description |
| --- | --- |
| **Name** | Friendly name for the device (e.g. `Piano`). |

That's the only setup question. Everything else is a **live control on the device page** (and remembers its value across restarts):

| Entity | What it does |
| --- | --- |
| **Motor** (switch) | Run / stop the motor. |
| **Speed** (number) | Run speed, 1–100 %. Defaults to a gear‑safe **50 %**. |
| **Reverse** (switch) | Off = forward, on = reverse direction. |
| **Brake on stop** (switch) | Off = float/coast, on = brake/hold when stopped. |
| **Motor port** (number) | Hub port the motor is on (**A=0, B=1, C=2, D=3**). |
| **Connection** (switch) | Connect / disconnect the hub. |
| **Connected** (binary sensor) | Live Bluetooth connection status. |

> [!CAUTION]
> Full speed (100 %) will skip the LEGO Piano (21323) gears. Keep the Speed at or near the default 50 % for that set.

> **Note:** A LEGO hub only allows one Bluetooth connection at a time. If you
> were previously controlling the hub from custom ESPHome firmware, disable that
> connection first so this integration can connect.

## Replacing the old play/stop automations

If you came here from automations that pressed `button.*_play` / `button.*_stop`,
replace those actions with the motor switch, e.g.:

```yaml
# Old
- action: button.press
  target:
    entity_id: button.lego_piano_controller_play

# New
- action: switch.turn_on
  target:
    entity_id: switch.piano_motor
```

## License

[MIT](LICENSE)

## Buy me a coffee

Did you find this helpful? Consider supporting additional development:

<a href="https://www.buymeacoffee.com/ajachiernoo" target="_blank">
  <img src="https://raw.githubusercontent.com/ajachierno/Lego-Power/main/brand/bmc_button.png" alt="Buy me a coffee" height="50">
</a>

<br><br>

<a href="https://www.buymeacoffee.com/ajachiernoo" target="_blank">
  <img src="https://raw.githubusercontent.com/ajachierno/Lego-Power/main/brand/buymeacoffee_qr.png" alt="Buy me a coffee QR code" width="200">
</a>
