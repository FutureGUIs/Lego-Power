"""Switch platform for the LEGO Power integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LegoPowerConfigEntry, lego
from .entity import (
    LegoPowerEntity,
    LegoPowerOutputEntity,
    async_setup_port_entities,
)
from .hub import LegoPowerHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LegoPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LEGO Power switches."""
    async_add_entities([LegoPowerConnectionSwitch(entry.runtime_data)])

    def _factory(hub: LegoPowerHub, port: int, kind: str) -> list[Entity]:
        if kind != lego.KIND_MOTOR:
            return []
        output = hub.get_output(port, kind)
        return [
            LegoPowerMotorSwitch(hub, output),
            LegoPowerReverseSwitch(hub, output),
            LegoPowerBrakeSwitch(hub, output),
        ]

    async_setup_port_entities(hass, entry, async_add_entities, _factory)


class LegoPowerConnectionSwitch(LegoPowerEntity, SwitchEntity):
    """Switch that connects or disconnects the hub over Bluetooth."""

    _attr_translation_key = "connection"
    _attr_icon = "mdi:bluetooth"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hub: LegoPowerHub) -> None:
        """Initialise the connection switch."""
        super().__init__(hub)
        self._attr_unique_id = f"{hub.address}_connection"

    @property
    def is_on(self) -> bool:
        """Return True when the hub is connected."""
        return self._hub.connected

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Connect to the hub."""
        await self._hub.async_connect_safe()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disconnect from the hub."""
        await self._hub.async_disconnect()


class LegoPowerMotorSwitch(LegoPowerOutputEntity, SwitchEntity):
    """Switch that runs or stops the motor on one port."""

    _attr_translation_key = "motor"
    _attr_icon = "mdi:engine"

    def __init__(self, hub: LegoPowerHub, output) -> None:
        """Initialise the motor switch."""
        super().__init__(hub, output, "run")

    @property
    def is_on(self) -> bool:
        """Return True when the motor is running."""
        return self._output.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the motor (connecting first if needed)."""
        await self._output.async_set_on(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the motor."""
        await self._output.async_set_on(False)


class LegoPowerReverseSwitch(LegoPowerOutputEntity, SwitchEntity, RestoreEntity):
    """Toggle the motor direction (on = reverse, off = forward)."""

    _attr_translation_key = "reverse"
    _attr_icon = "mdi:swap-horizontal"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hub: LegoPowerHub, output) -> None:
        """Initialise the reverse toggle."""
        super().__init__(hub, output, "reverse")

    @property
    def available(self) -> bool:
        """Settings stay editable whatever is plugged in."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True when the direction is reversed."""
        return self._output.reverse

    async def async_added_to_hass(self) -> None:
        """Restore the last direction set by the user, if any."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in ("on", "off"):
            self._output.reverse = last.state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Run the motor in reverse."""
        await self._output.async_set_reverse(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Run the motor forward."""
        await self._output.async_set_reverse(False)


class LegoPowerBrakeSwitch(LegoPowerOutputEntity, SwitchEntity, RestoreEntity):
    """Toggle the stop behaviour (on = brake/hold, off = float/coast)."""

    _attr_translation_key = "brake"
    _attr_icon = "mdi:car-brake-hold"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hub: LegoPowerHub, output) -> None:
        """Initialise the brake toggle."""
        super().__init__(hub, output, "brake")

    @property
    def available(self) -> bool:
        """Settings stay editable whatever is plugged in."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True when the motor brakes on stop."""
        return self._output.brake_on_stop

    async def async_added_to_hass(self) -> None:
        """Restore the last stop behaviour set by the user, if any."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in ("on", "off"):
            self._output.brake_on_stop = last.state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Brake (actively hold) when the motor stops."""
        await self._output.async_set_brake_on_stop(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Float (coast) when the motor stops."""
        await self._output.async_set_brake_on_stop(False)
