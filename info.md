# LEGO Power

Control **LEGO® Powered Up** motors directly over Bluetooth from Home Assistant.

Each hub becomes a device. The integration asks the hub what is plugged into
each port and creates the matching controls:

- motors get a **run** switch, a live **speed** control (default 50%),
  **reverse** and **brake** toggles,
- an 88005 **Light** gets a dimmable light entity,
- plus **battery**, a per-port **device** sensor, a **Connection** switch and a
  **Connected** status sensor.

Supports multiple hubs, hot-plugging devices, and auto‑reconnect. Works with a
local Bluetooth adapter or an ESPHome Bluetooth proxy.

> **Tested only on the LEGO Piano (21323).** Running the motor at full speed will
> skip the piano gears — keep the Speed near the default 50%.

See the [README](https://github.com/ajachierno/Lego-Power) for setup details.
