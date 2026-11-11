"""Light platform for the LEGO Power integration (88005 Light)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LegoPowerConfigEntry, lego
from .entity import LegoPowerOutputEntity, async_setup_port_entities
from .hub import LegoPowerHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LegoPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LEGO Power lights."""

    def _factory(hub: LegoPowerHub, port: int, kind: str) -> list[Entity]:
        if kind != lego.KIND_LIGHT:
            return []
        return [LegoPowerLight(hub, hub.get_output(port, kind))]

    async_setup_port_entities(hass, entry, async_add_entities, _factory)


def _to_ha(percent: int) -> int:
    """Convert hub brightness (1..100) to Home Assistant's 1..255 scale."""
    return max(1, round(percent * 255 / 100))


def _to_hub(brightness: int) -> int:
    """Convert Home Assistant brightness (0..255) to the hub's 1..100 scale."""
    return max(1, min(100, round(brightness * 100 / 255)))


class LegoPowerLight(LegoPowerOutputEntity, LightEntity, RestoreEntity):
    """An 88005 Light plugged into a hub port."""

    _attr_translation_key = "light"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, hub: LegoPowerHub, output) -> None:
        """Initialise the light."""
        super().__init__(hub, output, "light")

    @property
    def is_on(self) -> bool:
        """Return True when the light is lit."""
        return self._output.is_on

    @property
    def brightness(self) -> int:
        """Return the brightness on Home Assistant's 0..255 scale."""
        return _to_ha(self._output.brightness)

    async def async_added_to_hass(self) -> None:
        """Restore the last brightness (the light itself starts off)."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and (value := last.attributes.get(ATTR_BRIGHTNESS)):
            self._output.brightness = _to_hub(int(value))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the light on, optionally at a new brightness."""
        if ATTR_BRIGHTNESS in kwargs:
            await self._output.async_set_brightness(_to_hub(kwargs[ATTR_BRIGHTNESS]))
        else:
            await self._output.async_set_on(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the light off."""
        await self._output.async_set_on(False)
