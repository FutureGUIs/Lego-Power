"""Config flow for the LEGO Power integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import (
    DOMAIN,
    LEGO_HUB_SERVICE_UUID,
    LEGO_MANUFACTURER_ID,
)


def _is_lego_hub(info: BluetoothServiceInfoBleak) -> bool:
    """Return True if the advertisement looks like a LEGO Powered Up hub."""
    if LEGO_HUB_SERVICE_UUID in info.service_uuids:
        return True
    return LEGO_MANUFACTURER_ID in info.manufacturer_data


class LegoPowerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the LEGO Power config flow.

    Motor settings (port, speed, direction, stop behaviour) are exposed as
    live entities on the device page, so the flow only needs to identify the
    hub and give it a name.
    """

    VERSION = 2

    def __init__(self) -> None:
        """Initialise the flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a hub discovered over Bluetooth."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_name()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow started by the user; let them pick a hub."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._discovery_info = self._discovered.get(address)
            return await self.async_step_name()

        current_addresses = self._async_current_ids()
        devices: dict[str, str] = {}
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current_addresses or not _is_lego_hub(info):
                continue
            self._discovered[info.address] = info
            devices[info.address] = f"{info.name or 'LEGO hub'} ({info.address})"

        if not devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(devices)}),
        )

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Name the device and create the entry."""
        if user_input is not None:
            address = self.unique_id
            assert address is not None
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={CONF_ADDRESS: address},
            )

        default_name = "LEGO Power"
        if self._discovery_info and self._discovery_info.name:
            default_name = self._discovery_info.name

        return self.async_show_form(
            step_id="name",
            data_schema=vol.Schema(
                {vol.Required(CONF_NAME, default=default_name): str}
            ),
            description_placeholders={"name": default_name},
        )
