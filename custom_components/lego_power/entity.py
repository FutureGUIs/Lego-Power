"""Base entities and port-discovery plumbing for the LEGO Power integration."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LegoPowerConfigEntry, lego
from .const import DOMAIN, MANUFACTURER
from .hub import LegoPowerHub, PortOutput

# Pseudo-kind for the per-port "attached device" diagnostic sensor.
KIND_IO = "io"
_KINDS = (lego.KIND_MOTOR, lego.KIND_LIGHT, KIND_IO)


def port_unique_id(hub: LegoPowerHub, port: int, kind: str, role: str) -> str:
    """Return the unique ID of a per-port entity."""
    return f"{hub.address}_p{port}_{kind}_{role}"


class LegoPowerEntity(Entity):
    """Common base for all LEGO Power entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: LegoPowerHub) -> None:
        """Initialise the entity."""
        self._hub = hub
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub.address)},
            connections={(CONNECTION_BLUETOOTH, hub.address)},
            name=hub.name,
            manufacturer=MANUFACTURER,
            model="Powered Up Hub",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to hub state changes."""
        await super().async_added_to_hass()
        self.async_on_remove(self._hub.register_callback(self.async_write_ha_state))


class LegoPowerPortEntity(LegoPowerEntity):
    """Base for entities bound to one port of the hub."""

    def __init__(self, hub: LegoPowerHub, port: int, kind: str, role: str) -> None:
        """Initialise the per-port entity."""
        super().__init__(hub)
        self._port = port
        self._attr_unique_id = port_unique_id(hub, port, kind, role)
        self._attr_translation_placeholders = {"port": lego.port_label(port)}


class LegoPowerOutputEntity(LegoPowerPortEntity):
    """Base for entities that control a motor or light output."""

    def __init__(self, hub: LegoPowerHub, output: PortOutput, role: str) -> None:
        """Initialise the output entity."""
        super().__init__(hub, output.port, output.kind, role)
        self._output = output

    @property
    def available(self) -> bool:
        """Return True when a matching device is on this port."""
        return self._output.available


EntityFactory = Callable[[LegoPowerHub, int, str], Iterable[Entity]]


@callback
def async_setup_port_entities(
    hass: HomeAssistant,
    entry: LegoPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: EntityFactory,
) -> None:
    """Create entities for each (port, kind) the hub has or previously had.

    ``factory(hub, port, kind)`` returns the entities this platform provides
    for that port and kind (often none). It is called for every port/kind
    already in the entity registry, so entities survive a restart while their
    device is unplugged, and again whenever the hub reports a device attach.
    """
    hub = entry.runtime_data
    created: set[str] = set()

    @callback
    def _add(port: int, kind: str) -> None:
        new = [
            entity
            for entity in factory(hub, port, kind)
            if entity.unique_id not in created
        ]
        if new:
            created.update(entity.unique_id for entity in new)
            async_add_entities(new)

    @callback
    def _on_attach(port: int, io_type: int) -> None:
        if not lego.is_external_port(port):
            return
        _add(port, KIND_IO)
        if (kind := lego.io_type_kind(io_type)) is not None:
            _add(port, kind)

    # Ports known from earlier runs.
    pattern = re.compile(
        rf"^{re.escape(hub.address)}_p(\d+)_({'|'.join(_KINDS)})_"
    )
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if match := pattern.match(reg_entry.unique_id):
            _add(int(match.group(1)), match.group(2))

    # Ports the hub has already announced on this connection.
    for port, io_type in list(hub.ports.items()):
        _on_attach(port, io_type)

    entry.async_on_unload(hub.register_port_listener(_on_attach))
