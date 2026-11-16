"""Base entities: one device per camera, plus one for the watchdog itself."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CameraState, WatchdogCoordinator


class CameraEntity(CoordinatorEntity[WatchdogCoordinator]):
    """An entity that belongs to one watched camera."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WatchdogCoordinator, mac: str, key: str) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{mac}_{key}"
        cam = coordinator.cameras[mac]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=f"Vakt {cam.name}",
            manufacturer="UniFi Tapo Watchdog",
            model="Kameravakt",
            via_device=(DOMAIN, coordinator.entry.entry_id),
        )

    @property
    def cam(self) -> CameraState:
        return self.coordinator.cameras[self._mac]


class HubEntity(CoordinatorEntity[WatchdogCoordinator]):
    """An entity that belongs to the watchdog as a whole."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WatchdogCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name="UniFi Tapo Watchdog",
            manufacturer="UniFi Tapo Watchdog",
            model="Vakt",
        )
