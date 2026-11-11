"""Constants for the LEGO Power integration."""

from __future__ import annotations

DOMAIN = "lego_power"
MANUFACTURER = "LEGO"

# LEGO Wireless Protocol v3 (Powered Up) BLE identifiers.
# https://lego.github.io/lego-ble-wireless-protocol-docs/
LEGO_HUB_SERVICE_UUID = "00001623-1212-efde-1623-785feabcd123"
LEGO_HUB_CHARACTERISTIC_UUID = "00001624-1212-efde-1623-785feabcd123"
# Bluetooth SIG company identifier for "LEGO System A/S" (0x0397).
LEGO_MANUFACTURER_ID = 919

# Defaults for newly discovered outputs. Every setting is a live entity on
# the device page that restores its own state across restarts.
#
# The motor speed default mirrors the original LEGO Piano (21323) firmware
# this integration was built from: running that motor at full speed makes the
# gears skip, so the default is deliberately 50 %.
DEFAULT_SPEED = 50
DEFAULT_LIGHT_BRIGHTNESS = 100

# Bounds.
MIN_SPEED = 1
MAX_SPEED = 100
