"""Master switch: when off, the watchdog only watches and never acts."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import WatchdogConfigEntry
from .entity import HubEntity


async def async_setup_entry(hass: HomeAssistant, entry: WatchdogConfigEntry, add: AddEntitiesCallback) -> None:
    add([EnabledSwitch(entry.runtime_data)])


class EnabledSwitch(HubEntity, SwitchEntity, RestoreEntity):
    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "enabled")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.coordinator.enabled = last.state != "off"

    @property
    def is_on(self) -> bool:
        return self.coordinator.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.enabled = False
        self.async_write_ha_state()
