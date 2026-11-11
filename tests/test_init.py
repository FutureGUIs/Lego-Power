"""End-to-end tests: port discovery creates the right entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lego_power import lego
from custom_components.lego_power.const import DOMAIN

from .conftest import ADDRESS

MOTOR_ON_A = bytes.fromhex("0f0004000126000000001000000010")  # medium linear motor
LIGHT_ON_B = bytes.fromhex("0f0004010108000000001000000010")  # 88005 light
HUB_LED = bytes.fromhex("0f0004320117000000001000000010")  # internal port, ignored
BATTERY = bytes.fromhex("060001060657")


async def _setup(hass: HomeAssistant, version: int = 2) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="City Hub",
        data={CONF_ADDRESS: ADDRESS},
        unique_id=ADDRESS,
        version=version,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_motor_and_light_discovered(hass: HomeAssistant, fake_client) -> None:
    fake_client.on_subscribe = [MOTOR_ON_A, LIGHT_ON_B, HUB_LED, BATTERY]
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    states = {s.entity_id: s for s in hass.states.async_all()}
    assert "switch.city_hub_port_a_motor" in states
    assert "number.city_hub_port_a_speed" in states
    assert "light.city_hub_port_b_light" in states
    # The light port must not get motor controls, and vice versa.
    assert "switch.city_hub_port_b_motor" not in states
    assert "light.city_hub_port_a_light" not in states
    assert states["sensor.city_hub_port_a_device"].state == "Medium linear motor"
    assert states["sensor.city_hub_port_b_device"].state == "Light"
    assert states["sensor.city_hub_battery"].state == "87"
    assert not any("port_51" in e or "port_50" in e for e in states)

    # Light: on at ~50 % brightness -> brightness 50 on port B.
    fake_client.writes.clear()
    await hass.services.async_call(
        "light", "turn_on",
        {"entity_id": "light.city_hub_port_b_light", "brightness": 128},
        blocking=True,
    )
    assert fake_client.writes == [lego.set_light_brightness(1, 50)]
    assert hass.states.get("light.city_hub_port_b_light").state == "on"

    # Motor: on at default 50 % forward on port A, independent of the light.
    fake_client.writes.clear()
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.city_hub_port_a_motor"},
        blocking=True,
    )
    assert fake_client.writes == [lego.set_motor_power(0, 50)]
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.city_hub_port_a_speed", "value": 80},
        blocking=True,
    )
    assert fake_client.writes[-1] == lego.set_motor_power(0, 80)
    assert hass.states.get("light.city_hub_port_b_light").state == "on"

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.city_hub_port_b_light"},
        blocking=True,
    )
    assert fake_client.writes[-1] == lego.set_light_brightness(1, 0)


async def test_hot_plug_and_unplug(hass: HomeAssistant, fake_client) -> None:
    fake_client.on_subscribe = [MOTOR_ON_A]
    await _setup(hass)
    assert hass.states.get("light.city_hub_port_b_light") is None

    fake_client.push(LIGHT_ON_B)
    await hass.async_block_till_done()
    assert hass.states.get("light.city_hub_port_b_light").state == "off"

    fake_client.push(bytes.fromhex("0500040100"))  # port B detached
    await hass.async_block_till_done()
    assert hass.states.get("light.city_hub_port_b_light").state == "unavailable"
    assert hass.states.get("sensor.city_hub_port_b_device").state == "Nothing attached"

    # Swap a train motor into port B: motor controls appear for B.
    fake_client.push(bytes.fromhex("0f0004010102000000001000000010"))
    await hass.async_block_till_done()
    assert hass.states.get("switch.city_hub_port_b_motor").state == "off"
    assert hass.states.get("sensor.city_hub_port_b_device").state == "Train motor"


async def test_entities_restored_after_restart(hass: HomeAssistant, fake_client) -> None:
    """A known port keeps its entities even if nothing is plugged in now."""
    registry = er.async_get(hass)
    entry = MockConfigEntry(
        domain=DOMAIN, title="City Hub", data={CONF_ADDRESS: ADDRESS},
        unique_id=ADDRESS, version=2,
    )
    entry.add_to_hass(hass)
    registry.async_get_or_create(
        "light", DOMAIN, f"{ADDRESS}_p1_light_light", config_entry=entry,
        suggested_object_id="city_hub_port_b_light",
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("light.city_hub_port_b_light").state == "unavailable"


async def test_migration_removes_legacy_entities(hass: HomeAssistant, fake_client) -> None:
    registry = er.async_get(hass)
    entry = MockConfigEntry(
        domain=DOMAIN, title="City Hub", data={CONF_ADDRESS: ADDRESS},
        unique_id=ADDRESS, version=1,
    )
    entry.add_to_hass(hass)
    for suffix in ("motor", "connection"):
        registry.async_get_or_create(
            "switch", DOMAIN, f"{ADDRESS}_{suffix}", config_entry=entry
        )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 2
    assert registry.async_get_entity_id("switch", DOMAIN, f"{ADDRESS}_motor") is None
    assert registry.async_get_entity_id("switch", DOMAIN, f"{ADDRESS}_connection")
