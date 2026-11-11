"""Sensor platform for the LEGO Power integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LegoPowerConfigEntry, lego
from .entity import (
    KIND_IO,
    LegoPowerEntity,
    LegoPowerPortEntity,
    async_setup_port_entities,
)
from .hub import LegoPowerHub

NOTHING_ATTACHED = "Nothing attached"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LegoPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LEGO Power sensors."""
    async_add_entities([LegoPowerBatterySensor(entry.runtime_data)])

    def _factory(hub: LegoPowerHub, port: int, kind: str) -> list[Entity]:
        if kind != KIND_IO:
            return []
        return [LegoPowerPortDeviceSensor(hub, port)]

    async_setup_port_entities(hass, entry, async_add_entities, _factory)


class LegoPowerBatterySensor(LegoPowerEntity, SensorEntity):
    """Battery level reported by the hub."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: LegoPowerHub) -> None:
        """Initialise the battery sensor."""
        super().__init__(hub)
        self._attr_unique_id = f"{hub.address}_battery"

    @property
    def available(self) -> bool:
        """Return True once the hub has reported a level on this link."""
        return self._hub.connected and self._hub.battery is not None

    @property
    def native_value(self) -> int | None:
        """Return the battery percentage."""
        return self._hub.battery


class LegoPowerPortDeviceSensor(LegoPowerPortEntity, SensorEntity):
    """Shows which device the hub reports on a port."""

    _attr_translation_key = "port_device"
    _attr_icon = "mdi:usb-port"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: LegoPowerHub, port: int) -> None:
        """Initialise the port device sensor."""
        super().__init__(hub, port, KIND_IO, "device")

    @property
    def available(self) -> bool:
        """Only meaningful while connected."""
        return self._hub.connected

    @property
    def native_value(self) -> str:
        """Return the name of the attached device."""
        io_type = self._hub.ports.get(self._port)
        if io_type is None:
            return NOTHING_ATTACHED
        return lego.io_type_name(io_type)

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Expose the raw IO type ID, handy for unsupported devices."""
        io_type = self._hub.ports.get(self._port)
        return {"io_type": None if io_type is None else f"0x{io_type:04X}"}
