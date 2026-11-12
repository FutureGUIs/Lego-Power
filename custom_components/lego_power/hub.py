"""Bluetooth connection manager for a single LEGO Powered Up hub."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import lego
from .const import (
    DEFAULT_LIGHT_BRIGHTNESS,
    DEFAULT_SPEED,
    LEGO_HUB_CHARACTERISTIC_UUID,
    MAX_SPEED,
    MIN_SPEED,
)

_LOGGER = logging.getLogger(__name__)

# How many times bleak-retry-connector retries a single connection attempt.
_CONNECT_ATTEMPTS = 3

PortListener = Callable[[int, int], None]


class LegoPowerConnectionError(HomeAssistantError):
    """Raised when the hub cannot be reached over Bluetooth."""


class PortOutput:
    """State for one controllable output (a motor or a light) on one port."""

    def __init__(self, hub: LegoPowerHub, port: int, kind: str) -> None:
        """Initialise the output with default settings."""
        self.hub = hub
        self.port = port
        self.kind = kind
        self.label = lego.port_label(port)
        # Shared "on" flag: motor running / light lit.
        self.on = False
        # Motor settings.
        self.speed = DEFAULT_SPEED
        self.reverse = False
        self.brake_on_stop = False
        # Light settings.
        self.brightness = DEFAULT_LIGHT_BRIGHTNESS

    @property
    def signed_power(self) -> int:
        """Return the motor power (-100..100) including direction."""
        return -self.speed if self.reverse else self.speed

    @property
    def is_on(self) -> bool:
        """Return True when the output is running/lit on a live link."""
        return self.on and self.hub.connected

    @property
    def available(self) -> bool:
        """Return True when the hub is connected with a matching device here.

        While the hub is off or out of range the output is unavailable; the
        integration reconnects on its own as soon as the hub advertises again.
        """
        return self.hub.connected and self.hub.port_kind(self.port) == self.kind

    def command(self) -> bytes:
        """Return the message that applies the current state to the hub."""
        if self.kind == lego.KIND_LIGHT:
            return lego.set_light_brightness(
                self.port, self.brightness if self.on else 0
            )
        if self.on:
            return lego.set_motor_power(self.port, self.signed_power)
        return lego.stop_motor(self.port, brake=self.brake_on_stop)

    def off_command(self) -> bytes:
        """Return the message that switches this output off."""
        if self.kind == lego.KIND_LIGHT:
            return lego.set_light_brightness(self.port, 0)
        return lego.stop_motor(self.port, brake=self.brake_on_stop)

    async def async_set_on(self, on: bool) -> None:
        """Run/stop the motor or switch the light on/off."""
        if on and not self.hub.connected:
            await self.hub.async_connect()
        self.on = on
        if self.hub.connected:
            await self.hub.async_write(self.command())
        self.hub.notify()

    async def async_set_speed(self, speed: int) -> None:
        """Set the motor speed, applying it live if running."""
        self.speed = max(MIN_SPEED, min(MAX_SPEED, int(speed)))
        await self._async_reapply()

    async def async_set_reverse(self, reverse: bool) -> None:
        """Set the motor direction, applying it live if running."""
        self.reverse = bool(reverse)
        await self._async_reapply()

    async def async_set_brake_on_stop(self, brake: bool) -> None:
        """Set the stop behaviour (applies on the next stop)."""
        self.brake_on_stop = bool(brake)
        self.hub.notify()

    async def async_set_brightness(self, brightness: int) -> None:
        """Set the light brightness (1..100) and switch it on."""
        self.brightness = max(1, min(100, int(brightness)))
        await self.async_set_on(True)

    async def _async_reapply(self) -> None:
        if self.is_on:
            await self.hub.async_write(self.command())
        self.hub.notify()


class LegoPowerHub:
    """Manage the BLE link to one LEGO hub and the devices on its ports."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        """Initialise the hub controller."""
        self.hass = hass
        self.address = address
        self.name = name

        # Port ID -> IO type ID, as reported by Hub Attached I/O messages.
        self.ports: dict[int, int] = {}
        self.battery: int | None = None
        self._outputs: dict[tuple[int, str], PortOutput] = {}

        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()
        self._should_stay_connected = False
        self._callbacks: set[Callable[[], None]] = set()
        self._port_listeners: set[PortListener] = set()

    # -- state ------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """Return True when an active BLE connection exists."""
        return self._client is not None and self._client.is_connected

    @property
    def connecting(self) -> bool:
        """Return True while a connection attempt is in progress."""
        return self._lock.locked()

    @property
    def should_stay_connected(self) -> bool:
        """Return True when the hub is meant to maintain a connection."""
        return self._should_stay_connected

    def port_kind(self, port: int) -> str | None:
        """Return the output kind of the device currently on ``port``."""
        io_type = self.ports.get(port)
        return None if io_type is None else lego.io_type_kind(io_type)

    def get_output(self, port: int, kind: str) -> PortOutput:
        """Return (creating if needed) the output state for ``port``/``kind``."""
        key = (port, kind)
        if key not in self._outputs:
            self._outputs[key] = PortOutput(self, port, kind)
        return self._outputs[key]

    # -- listeners --------------------------------------------------------

    def register_callback(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a listener to be notified of state changes."""
        self._callbacks.add(callback)
        return lambda: self._callbacks.discard(callback)

    def register_port_listener(self, listener: PortListener) -> Callable[[], None]:
        """Register a listener called with (port, io_type) on device attach."""
        self._port_listeners.add(listener)
        return lambda: self._port_listeners.discard(listener)

    def notify(self) -> None:
        """Notify all registered listeners that state changed."""
        for callback in list(self._callbacks):
            callback()

    # -- connection -------------------------------------------------------

    async def async_connect(self) -> None:
        """Establish the BLE connection to the hub."""
        async with self._lock:
            if self.connected:
                return

            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if ble_device is None:
                raise LegoPowerConnectionError(
                    f"LEGO hub {self.address} was not found; "
                    "is it powered on and in range?"
                )

            try:
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    self.name,
                    disconnected_callback=self._handle_disconnect,
                    max_attempts=_CONNECT_ATTEMPTS,
                )
            except (BleakError, asyncio.TimeoutError) as err:
                raise LegoPowerConnectionError(
                    f"Could not connect to LEGO hub {self.address}: {err}"
                ) from err

            self._client = client
            self._should_stay_connected = True
            self.ports.clear()

            try:
                # Subscribing makes the hub announce every attached device.
                await client.start_notify(
                    LEGO_HUB_CHARACTERISTIC_UUID, self._handle_notification
                )
                await client.write_gatt_char(
                    LEGO_HUB_CHARACTERISTIC_UUID,
                    lego.enable_battery_updates(),
                    response=False,
                )
            except (BleakError, asyncio.TimeoutError):
                _LOGGER.warning(
                    "Could not subscribe to notifications on %s; "
                    "attached devices will not be discovered",
                    self.address,
                    exc_info=True,
                )

        _LOGGER.debug("Connected to LEGO hub %s (%s)", self.name, self.address)
        self.notify()

    async def async_connect_safe(self) -> None:
        """Attempt to connect, swallowing connection errors.

        Marks the hub as wanted, so a failed attempt is retried automatically
        when the hub next advertises (e.g. once it is switched on).
        """
        self._should_stay_connected = True
        try:
            await self.async_connect()
        except LegoPowerConnectionError as err:
            _LOGGER.debug("Connect attempt for %s failed: %s", self.address, err)

    async def async_disconnect(self) -> None:
        """Switch every output off and disconnect, and stay disconnected."""
        self._should_stay_connected = False
        async with self._lock:
            client = self._client
            self._client = None
            if client is not None and client.is_connected:
                for output in self._outputs.values():
                    if not output.on:
                        continue
                    try:
                        await client.write_gatt_char(
                            LEGO_HUB_CHARACTERISTIC_UUID,
                            output.off_command(),
                            response=False,
                        )
                    except (BleakError, asyncio.TimeoutError):
                        _LOGGER.debug(
                            "Error stopping port %s on disconnect",
                            output.label,
                            exc_info=True,
                        )
                try:
                    await client.disconnect()
                except (BleakError, asyncio.TimeoutError):
                    _LOGGER.debug("Error during disconnect", exc_info=True)
            self._reset_link_state()
        self.notify()

    async def async_write(self, data: bytes) -> None:
        """Write a raw command to the hub characteristic."""
        client = self._client
        if client is None or not client.is_connected:
            raise LegoPowerConnectionError("Not connected to the LEGO hub")
        try:
            await client.write_gatt_char(
                LEGO_HUB_CHARACTERISTIC_UUID, data, response=False
            )
        except (BleakError, asyncio.TimeoutError) as err:
            raise LegoPowerConnectionError(
                f"Failed to send command to {self.address}: {err}"
            ) from err

    def _reset_link_state(self) -> None:
        """Forget everything that only holds while connected."""
        self.ports.clear()
        for output in self._outputs.values():
            output.on = False

    def _handle_disconnect(self, _client: BleakClientWithServiceCache) -> None:
        """Handle an unexpected disconnect from the hub."""
        _LOGGER.debug("LEGO hub %s disconnected", self.address)
        self._client = None
        self._reset_link_state()
        self.notify()
        if self._should_stay_connected:
            self.hass.async_create_task(self.async_connect_safe())

    def _handle_notification(self, _sender: object, data: bytearray) -> None:
        """Handle inbound notifications from the hub."""
        _LOGGER.debug("Notification from %s: %s", self.address, data.hex())
        message = lego.parse_message(data)

        if isinstance(message, lego.AttachedIO):
            if message.io_type is None:
                _LOGGER.debug("Port %s: device detached", message.port)
                self.ports.pop(message.port, None)
                output_kinds = [k for (p, k) in self._outputs if p == message.port]
                for kind in output_kinds:
                    self._outputs[(message.port, kind)].on = False
            else:
                _LOGGER.debug(
                    "Port %s: %s attached",
                    lego.port_label(message.port),
                    lego.io_type_name(message.io_type),
                )
                self.ports[message.port] = message.io_type
                for listener in list(self._port_listeners):
                    listener(message.port, message.io_type)
            self.notify()

        elif isinstance(message, lego.BatteryLevel):
            self.battery = message.percent
            self.notify()
