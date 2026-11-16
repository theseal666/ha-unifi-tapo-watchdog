"""Per camera: status, what the watchdog did last, and how often."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WatchdogConfigEntry
from .const import ACTION_KICK, ACTION_NOTIFY_ONLY, ACTION_POWER_CYCLE, STATE_OFFLINE, STATE_OK, STATE_ZOMBIE
from .entity import CameraEntity, HubEntity


async def async_setup_entry(hass: HomeAssistant, entry: WatchdogConfigEntry, add: AddEntitiesCallback) -> None:
    c = entry.runtime_data
    entities: list[SensorEntity] = [CamerasDownSensor(c)]
    for mac in c.cameras:
        entities += [StatusSensor(c, mac), LastActionSensor(c, mac), ActionsTodaySensor(c, mac)]
    add(entities)


class StatusSensor(CameraEntity, SensorEntity):
    """ok / zombie (on Wi-Fi but silent) / offline (not on Wi-Fi)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATE_OK, STATE_ZOMBIE, STATE_OFFLINE]

    def __init__(self, coordinator, mac: str) -> None:
        super().__init__(coordinator, mac, "status")

    @property
    def native_value(self) -> str:
        return self.cam.state


class LastActionSensor(CameraEntity, SensorEntity):
    """When the watchdog last acted on this camera; the reason is in the attributes."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, mac: str) -> None:
        super().__init__(coordinator, mac, "last_action")

    @property
    def native_value(self) -> datetime | None:
        return self.cam.last_action_at

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "action": {ACTION_KICK: "kick", ACTION_POWER_CYCLE: "power_cycle", ACTION_NOTIFY_ONLY: "notify_only"}.get(
                self.cam.last_action or "", None
            ),
            "reason": self.cam.last_action_reason,
            "actions_total": self.cam.actions_total,
        }


class ActionsTodaySensor(CameraEntity, SensorEntity):
    """Kicks and power cycles today (resets at midnight)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, mac: str) -> None:
        super().__init__(coordinator, mac, "actions_today")

    @property
    def native_value(self) -> int:
        return self.cam.actions_today


class CamerasDownSensor(HubEntity, SensorEntity):
    """How many watched cameras do not answer right now."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "cameras_down")

    @property
    def native_value(self) -> int:
        return sum(1 for c in self.coordinator.cameras.values() if c.state != STATE_OK)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"down": [c.name for c in self.coordinator.cameras.values() if c.state != STATE_OK]}
