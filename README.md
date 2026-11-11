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

- 🔍 **Port discovery** — the hub reports what is plugged into each port, and
  the right controls appear automatically: motor controls for a motor, a
  dimmable light for an 88005 Light. Plug in or swap devices while connected
  and the entities follow.
- 🎛️ **Per-port motor controls** — run/stop switch, live speed slider
  (1–100 %, defaults to a gear‑safe 50 %), reverse and brake toggles.
- 💡 **Lights** — the 88005 Light is a real `light` entity with brightness.
- 🔋 **Battery** level and a **Port X device** diagnostic sensor per port.
- 🔌 **Connection** switch and **Connected** binary sensor.
- ➕ **Multiple devices** — add as many hubs as you like, one config entry each.
- 🔁 **Auto‑reconnect** — re‑establishes the link when the hub comes back in range.

## How it works

LEGO Powered Up hubs (City Hub 88009, Technic Hub 88012, Boost Move Hub 88006,
etc.) expose a single BLE service (`00001623-…`) with one characteristic
(`00001624-…`). This integration sends *Port Output Commands*
(`WriteDirectModeData`, direct mode) to drive the motor or light on each port.

On connect the integration subscribes to the hub's notifications. The hub then
sends a *Hub Attached I/O* message for every device on its ports (and again
whenever one is plugged in or removed); each one carries an IO type ID, which
decides which entities are created for that port. Lights are driven with the
same direct-mode command as motors, where the value is brightness instead of
power.

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

That's the only setup question. Entities are created per port (A, B, C, D)
based on what the hub reports, and settings remember their value across
restarts:

| Entity | Created when | What it does |
| --- | --- | --- |
| **Port X motor** (switch) | a motor is on port X | Run / stop the motor. |
| **Port X speed** (number) | a motor is on port X | Run speed, 1–100 %. Defaults to a gear‑safe **50 %**. |
| **Port X reverse** (switch) | a motor is on port X | Off = forward, on = reverse direction. |
| **Port X brake on stop** (switch) | a motor is on port X | Off = float/coast, on = brake/hold when stopped. |
| **Port X light** (light) | an 88005 Light is on port X | On / off with brightness. |
| **Port X device** (sensor) | anything is on port X | What the hub reports on that port, with the raw `io_type`. |
| **Battery** (sensor) | always | Hub battery level. |
| **Connection** (switch) | always | Connect / disconnect the hub. |
| **Connected** (binary sensor) | always | Live Bluetooth connection status. |

Entities for a port stay registered when its device is unplugged and show as
unavailable until it is plugged back in.

Supported devices: Powered Up / Technic motors (88008, 88011 train motor,
88013, 88014, Technic angular motors, Boost motors) and the 88005 Light. Any
other device still shows up in its **Port X device** sensor, so its IO type can
be added later.

> [!CAUTION]
> Full speed (100 %) will skip the LEGO Piano (21323) gears. Keep the Speed at or near the default 50 % for that set.

> **Note:** A LEGO hub only allows one Bluetooth connection at a time. If you
> were previously controlling the hub from custom ESPHome firmware, disable that
> connection first so this integration can connect.

## Upgrading from 1.x

1.x exposed a single **Motor** switch with a configurable **Motor port**. In
2.0 those entities (Motor, Speed, Reverse, Brake on stop, Motor port) are
removed and replaced by per-port entities. Update automations accordingly, e.g.
`switch.piano_motor` → `switch.piano_port_a_motor`. Direction now defaults to
forward; turn on **Port A reverse** once if your set needs reverse (the LEGO
Piano does).

## Development

```bash
pip install pytest-homeassistant-custom-component
pytest tests --asyncio-mode=auto
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
