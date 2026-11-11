"""Number platform for the LEGO Power integration."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LegoPowerConfigEntry, lego
from .const import MAX_SPEED, MIN_SPEED
from .entity import LegoPowerOutputEntity, async_setup_port_entities
from .hub import LegoPowerHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LegoPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LEGO Power number entities."""

    def _factory(hub: LegoPowerHub, port: int, kind: str) -> list[Entity]:
        if kind != lego.KIND_MOTOR:
            return []
        return [LegoPowerSpeedNumber(hub, hub.get_output(port, kind))]

    async_setup_port_entities(hass, entry, async_add_entities, _factory)


class LegoPowerSpeedNumber(LegoPowerOutputEntity, RestoreNumber):
    """Live speed control for a motor (percentage of full power).

    Running the motor at full speed can make the LEGO Piano (21323) gears
    skip, so the default is a conservative 50 %.
    """

    _attr_translation_key = "speed"
    _attr_icon = "mdi:speedometer"
    _attr_native_min_value = MIN_SPEED
    _attr_native_max_value = MAX_SPEED
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, hub: LegoPowerHub, output) -> None:
        """Initialise the speed control."""
        super().__init__(hub, output, "speed")

    @property
    def available(self) -> bool:
        """Settings stay editable whatever is plugged in."""
        return True

    @property
    def native_value(self) -> float:
        """Return the current run speed percentage."""
        return float(self._output.speed)

    async def async_added_to_hass(self) -> None:
        """Restore the last speed set by the user, if any."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._output.speed = int(last.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the run speed (applied live if the motor is running)."""
        await self._output.async_set_speed(int(value))
