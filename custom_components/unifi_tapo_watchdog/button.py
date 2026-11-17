"""Per camera: kick it off Wi-Fi now."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WatchdogConfigEntry
from .entity import CameraEntity


async def async_setup_entry(hass: HomeAssistant, entry: WatchdogConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    add(KickButton(coordinator, mac) for mac in coordinator.cameras)


class KickButton(CameraEntity, ButtonEntity):
    _attr_icon = "mdi:wifi-refresh"

    def __init__(self, coordinator, mac: str) -> None:
        super().__init__(coordinator, mac, "kick")

    async def async_press(self) -> None:
        await self.coordinator.async_kick(self.cam, "kick button pressed", manual=True)
        await self.coordinator.async_request_refresh()
