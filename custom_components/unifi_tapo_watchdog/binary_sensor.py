"""Per camera: does it answer right now?"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WatchdogConfigEntry
from .entity import CameraEntity


async def async_setup_entry(hass: HomeAssistant, entry: WatchdogConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    add(ReachableSensor(coordinator, mac) for mac in coordinator.cameras)


class ReachableSensor(CameraEntity, BinarySensorEntity):
    """On when the camera accepts a connection on the probe port (RTSP)."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, mac: str) -> None:
        super().__init__(coordinator, mac, "reachable")

    @property
    def is_on(self) -> bool:
        return self.cam.reachable

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        cam = self.cam
        return {
            "status": cam.state,
            "ip": cam.ip,
            "mac": cam.mac,
            "on_wifi": cam.associated,
            "ap_mac": cam.ap_mac,
            "signal_dbm": cam.signal,
            "down_since": cam.bad_since.isoformat() if cam.bad_since else None,
            "last_ok": cam.last_ok.isoformat() if cam.last_ok else None,
        }
