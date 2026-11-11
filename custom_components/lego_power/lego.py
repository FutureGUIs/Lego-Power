"""Helpers for building and parsing LEGO Wireless Protocol v3 messages.

Only the small subset of the protocol this integration needs is implemented.
See the official specification:
https://lego.github.io/lego-ble-wireless-protocol-docs/

Outputs are driven with "Port Output Commands" (message type ``0x81``) using
the ``WriteDirectModeData`` sub command (``0x51``) in mode ``0x00``. For motors
the value is signed power (-100..100); for the 88005 Light it is brightness
(0..100).

Inbound, the hub announces every attached device with a "Hub Attached I/O"
message (``0x04``) as soon as notifications are enabled, and again whenever a
device is plugged in or removed. That is what drives port discovery.
"""

from __future__ import annotations

from dataclasses import dataclass

# Common message fields.
HUB_ID = 0x00
MSG_HUB_PROPERTIES = 0x01
MSG_HUB_ATTACHED_IO = 0x04
MSG_PORT_OUTPUT_COMMAND = 0x81
# Startup (execute immediately, 0x10) + completion (request feedback, 0x01).
STARTUP_AND_COMPLETION = 0x11
SUBCMD_WRITE_DIRECT_MODE_DATA = 0x51
DIRECT_MODE = 0x00

# Hub property: battery percentage.
PROP_BATTERY_VOLTAGE = 0x06
PROP_OP_ENABLE_UPDATES = 0x02
PROP_OP_UPDATE = 0x06

# Hub Attached I/O events.
EVENT_DETACHED = 0x00
EVENT_ATTACHED = 0x01
EVENT_ATTACHED_VIRTUAL = 0x02

# Special power values understood by the hub.
POWER_FLOAT = 0  # Coast / let the motor spin freely.
POWER_BRAKE = 127  # Actively hold position.

# Ports at or above this ID are internal to the hub (LED, voltage, current,
# IMU, ...). Below it are the user-facing ports A, B, C, D.
FIRST_INTERNAL_PORT = 0x32

# Output kinds this integration knows how to control.
KIND_MOTOR = "motor"
KIND_LIGHT = "light"

# IO type IDs (Hub Attached I/O) -> (display name, output kind or None).
IO_TYPES: dict[int, tuple[str, str | None]] = {
    0x0001: ("Simple medium linear motor", KIND_MOTOR),
    0x0002: ("Train motor", KIND_MOTOR),
    0x0008: ("Light", KIND_LIGHT),
    0x0014: ("Voltage sensor", None),
    0x0015: ("Current sensor", None),
    0x0016: ("Piezo buzzer", None),
    0x0017: ("Hub RGB light", None),
    0x0022: ("Tilt sensor", None),
    0x0023: ("Motion sensor", None),
    0x0025: ("Color & distance sensor", None),
    0x0026: ("Medium linear motor", KIND_MOTOR),
    0x0027: ("Move Hub medium linear motor", KIND_MOTOR),
    0x0029: ("DUPLO train base motor", KIND_MOTOR),
    0x002E: ("Technic large linear motor", KIND_MOTOR),
    0x002F: ("Technic XL linear motor", KIND_MOTOR),
    0x0030: ("Technic medium angular motor", KIND_MOTOR),
    0x0031: ("Technic large angular motor", KIND_MOTOR),
    0x003D: ("Technic color sensor", None),
    0x003E: ("Technic distance sensor", None),
    0x003F: ("Technic force sensor", None),
    0x0041: ("Technic small angular motor", KIND_MOTOR),
    0x004B: ("Technic medium angular motor (grey)", KIND_MOTOR),
    0x004C: ("Technic large angular motor (grey)", KIND_MOTOR),
}


def io_type_name(io_type: int) -> str:
    """Return a human readable name for an IO type ID."""
    if io_type in IO_TYPES:
        return IO_TYPES[io_type][0]
    return f"Unknown device (0x{io_type:04X})"


def io_type_kind(io_type: int) -> str | None:
    """Return the controllable output kind for an IO type, if any."""
    entry = IO_TYPES.get(io_type)
    return entry[1] if entry else None


def is_external_port(port: int) -> bool:
    """Return True for user-facing ports (A, B, C, D)."""
    return port < FIRST_INTERNAL_PORT


def port_label(port: int) -> str:
    """Return the label printed on the hub for ``port`` (A, B, ...)."""
    if 0 <= port < 26:
        return chr(ord("A") + port)
    return str(port)


# ---------------------------------------------------------------------------
# Outbound messages
# ---------------------------------------------------------------------------


def _frame(body: bytes) -> bytes:
    """Prefix ``body`` with the message length (which includes itself)."""
    return bytes([len(body) + 1]) + body


def _signed_byte(value: int) -> int:
    """Return ``value`` (-128..127) as an unsigned byte (two's complement)."""
    return value & 0xFF


def _port_output(port: int, payload: bytes) -> bytes:
    """Build a Port Output / WriteDirectModeData message for ``port``."""
    return _frame(
        bytes(
            [
                HUB_ID,
                MSG_PORT_OUTPUT_COMMAND,
                port & 0xFF,
                STARTUP_AND_COMPLETION,
                SUBCMD_WRITE_DIRECT_MODE_DATA,
                DIRECT_MODE,
            ]
        )
        + payload
    )


def set_motor_power(port: int, power: int) -> bytes:
    """Build a command setting direct motor power (``-100``..``100``)."""
    power = max(-100, min(100, int(power)))
    return _port_output(port, bytes([_signed_byte(power)]))


def stop_motor(port: int, *, brake: bool = False) -> bytes:
    """Build a command stopping the motor (coast by default, or brake)."""
    value = POWER_BRAKE if brake else POWER_FLOAT
    return _port_output(port, bytes([_signed_byte(value)]))


def set_light_brightness(port: int, brightness: int) -> bytes:
    """Build a command setting a Light's brightness (``0``..``100``)."""
    brightness = max(0, min(100, int(brightness)))
    return _port_output(port, bytes([brightness]))


def enable_battery_updates() -> bytes:
    """Build a request for the hub to push battery percentage updates."""
    return _frame(
        bytes(
            [
                HUB_ID,
                MSG_HUB_PROPERTIES,
                PROP_BATTERY_VOLTAGE,
                PROP_OP_ENABLE_UPDATES,
            ]
        )
    )


# ---------------------------------------------------------------------------
# Inbound messages
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AttachedIO:
    """A device was attached to (``io_type`` set) or detached from a port."""

    port: int
    io_type: int | None

    @property
    def attached(self) -> bool:
        """Return True when this event is an attachment."""
        return self.io_type is not None


@dataclass(frozen=True)
class BatteryLevel:
    """Battery level of the hub, in percent."""

    percent: int


def parse_message(data: bytes | bytearray) -> AttachedIO | BatteryLevel | None:
    """Parse an inbound notification; return None for unhandled messages."""
    if len(data) < 3:
        return None
    # Lengths above 127 use a two-byte encoding (MSB of the first byte set).
    offset = 2 if data[0] & 0x80 else 1
    if len(data) < offset + 2:
        return None
    msg_type = data[offset + 1]
    payload = bytes(data[offset + 2 :])

    if msg_type == MSG_HUB_ATTACHED_IO and len(payload) >= 2:
        port, event = payload[0], payload[1]
        if event == EVENT_DETACHED:
            return AttachedIO(port=port, io_type=None)
        if event in (EVENT_ATTACHED, EVENT_ATTACHED_VIRTUAL) and len(payload) >= 4:
            io_type = int.from_bytes(payload[2:4], "little")
            return AttachedIO(port=port, io_type=io_type)
        return None

    if (
        msg_type == MSG_HUB_PROPERTIES
        and len(payload) >= 3
        and payload[0] == PROP_BATTERY_VOLTAGE
        and payload[1] == PROP_OP_UPDATE
    ):
        return BatteryLevel(percent=payload[2])

    return None
