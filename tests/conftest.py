"""Shared fixtures for LEGO Power tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow loading custom_components in every test."""
    return


class FakeClient:
    """Minimal stand-in for a connected BleakClient."""

    def __init__(self) -> None:
        self.is_connected = True
        self.writes: list[bytes] = []
        self.notify_cb = None
        self.on_subscribe: list[bytes] = []

    async def start_notify(self, _uuid, callback):
        self.notify_cb = callback
        # A real hub announces attached devices as soon as we subscribe.
        for msg in self.on_subscribe:
            callback(0, bytearray(msg))

    async def write_gatt_char(self, _uuid, data, response=False):
        self.writes.append(bytes(data))

    async def disconnect(self):
        self.is_connected = False

    def push(self, msg: bytes) -> None:
        self.notify_cb(0, bytearray(msg))


@pytest.fixture
def fake_client():
    """Patch the BLE stack so the hub 'connects' to a FakeClient."""
    client = FakeClient()
    with (
        patch(
            "custom_components.lego_power.bluetooth.async_address_present",
            return_value=True,
        ),
        patch(
            "custom_components.lego_power.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
        patch(
            "custom_components.lego_power.hub.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.lego_power.hub.establish_connection",
            AsyncMock(return_value=client),
        ),
        patch("homeassistant.loader.Integration.dependencies", []),
    ):
        yield client
