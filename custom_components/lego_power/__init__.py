"""The LEGO Power integration."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .hub import LegoPowerConnectionError, LegoPowerHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Unique ID suffixes of the single-motor entities from version 1.x, replaced
# by per-port entities discovered from the hub.
_LEGACY_SUFFIXES = ("motor", "speed", "port", "reverse", "brake")

type LegoPowerConfigEntry = ConfigEntry[LegoPowerHub]


async def async_setup_entry(
    hass: HomeAssistant, entry: LegoPowerConfigEntry
) -> bool:
    """Set up LEGO Power from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    hub = LegoPowerHub(hass, address=address, name=entry.title)

    if not bluetooth.async_address_present(hass, address, connectable=True):
        raise ConfigEntryNotReady(
            f"LEGO hub {address} is not currently in Bluetooth range"
        )

    try:
        await hub.async_connect()
    except LegoPowerConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = hub

    @callback
    def _async_on_advertisement(
        _service_info: BluetoothServiceInfoBleak,
        _change: BluetoothChange,
    ) -> None:
        """Reconnect automatically when the hub starts advertising again."""
        if hub.should_stay_connected and not hub.connected:
            hass.async_create_task(hub.async_connect_safe())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_on_advertisement,
            BluetoothCallbackMatcher(address=address, connectable=True),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LegoPowerConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_disconnect()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    if entry.version > 2:
        return False

    if entry.version == 1:
        # 1.x exposed one motor with a configurable port. Ports are now
        # discovered, so drop the old single-motor entities.
        registry = er.async_get(hass)
        address = entry.data[CONF_ADDRESS]
        legacy = {f"{address}_{suffix}" for suffix in _LEGACY_SUFFIXES}
        for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if reg_entry.unique_id in legacy:
                _LOGGER.info("Removing legacy entity %s", reg_entry.entity_id)
                registry.async_remove(reg_entry.entity_id)
        hass.config_entries.async_update_entry(entry, version=2)

    return True
