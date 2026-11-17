"""Watchdog logic: probe each camera, read UniFi, and act when one is stuck."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import socket
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import UniFiClient, UniFiError
from .const import (
    ACTION_KICK,
    ACTION_NOTIFY_ONLY,
    ACTION_POWER_CYCLE,
    CONF_CAMERAS,
    CONF_COOLDOWN,
    CONF_KICK_ENABLED,
    CONF_MAX_ACTIONS,
    CONF_NOTIFY_SERVICE,
    CONF_POWER_OFF_SECONDS,
    CONF_POWER_SWITCHES,
    CONF_PROBE_PORT,
    CONF_SCAN_INTERVAL,
    CONF_THRESHOLD,
    DEFAULT_COOLDOWN,
    DEFAULT_MAX_ACTIONS,
    DEFAULT_POWER_OFF_SECONDS,
    DEFAULT_PROBE_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_THRESHOLD,
    DOMAIN,
    EVENT_ACTION,
    CONF_PROBE_ATTEMPTS,
    CONF_PROBE_TIMEOUT,
    DEFAULT_PROBE_ATTEMPTS,
    DEFAULT_PROBE_TIMEOUT,
    PROBE_RETRY_DELAY,
    STATE_OFFLINE,
    STATE_OK,
    STATE_ZOMBIE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CameraState:
    """Everything the watchdog knows about one camera."""

    mac: str
    name: str
    state: str = STATE_OK
    ip: str | None = None
    last_good_ip: str | None = None
    ap_mac: str | None = None
    signal: int | None = None
    associated: bool = False
    reachable: bool = False
    bad_since: datetime | None = None
    last_ok: datetime | None = None
    last_action: str | None = None
    last_action_at: datetime | None = None
    last_action_reason: str | None = None
    actions_today: int = 0
    actions_total: int = 0
    notified_this_outage: bool = False
    action_day: str = field(default_factory=lambda: dt_util.now().date().isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "mac": self.mac,
            "name": self.name,
            "state": self.state,
            "ip": self.ip,
            "ap_mac": self.ap_mac,
            "signal": self.signal,
            "associated": self.associated,
            "reachable": self.reachable,
            "bad_since": self.bad_since,
            "last_ok": self.last_ok,
            "last_action": self.last_action,
            "last_action_at": self.last_action_at,
            "last_action_reason": self.last_action_reason,
            "actions_today": self.actions_today,
            "actions_total": self.actions_total,
        }


def _probe(ip: str, port: int, timeout: float, attempts: int) -> tuple[bool, str]:
    """Try a TCP connection to the camera (RTSP by default). Blocking: run in an executor.

    Runs in a worker thread so a busy Home Assistant event loop cannot make a
    camera look silent. A busy camera on Wi-Fi sometimes misses a single
    attempt, so it only counts as silent when every attempt fails.
    Returns (answered, what happened on each attempt).
    """
    notes: list[str] = []
    for attempt in range(1, max(1, attempts) + 1):
        if attempt > 1:
            time.sleep(PROBE_RETRY_DELAY)
        started = time.monotonic()
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                pass
        except TimeoutError:
            notes.append(f"attempt {attempt}: no answer within {timeout:g} s")
        except OSError as err:
            notes.append(f"attempt {attempt}: {err.strerror or err} after {time.monotonic() - started:.1f} s")
        else:
            notes.append(f"attempt {attempt}: ok in {(time.monotonic() - started) * 1000:.0f} ms")
            return True, "; ".join(notes)
    return False, "; ".join(notes)


class WatchdogCoordinator(DataUpdateCoordinator[dict[str, CameraState]]):
    """Polls UniFi and the cameras, and kicks or power-cycles stuck ones."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: UniFiClient) -> None:
        self.entry = entry
        self.client = client
        self.enabled = True
        self._busy: set[str] = set()
        opts = entry.options
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.cameras: dict[str, CameraState] = {
            mac: CameraState(mac=mac, name=name)
            for mac, name in opts.get(CONF_CAMERAS, {}).items()
        }

    # ---- options -------------------------------------------------------
    def _opt(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, default)

    # ---- polling -------------------------------------------------------
    async def _async_update_data(self) -> dict[str, CameraState]:
        try:
            connected = await self.client.connected_clients()
            known = await self.client.known_clients()
        except UniFiError as err:
            raise UpdateFailed(str(err)) from err

        port = int(self._opt(CONF_PROBE_PORT, DEFAULT_PROBE_PORT))
        timeout = float(self._opt(CONF_PROBE_TIMEOUT, DEFAULT_PROBE_TIMEOUT))
        attempts = int(self._opt(CONF_PROBE_ATTEMPTS, DEFAULT_PROBE_ATTEMPTS))
        now = dt_util.now()

        async def check(cam: CameraState) -> None:
            conn = connected.get(cam.mac)
            rec = known.get(cam.mac, {})
            cam.associated = conn is not None
            cam.ap_mac = (conn or {}).get("ap_mac")
            cam.signal = (conn or {}).get("signal")
            if rec.get("name"):
                cam.name = rec["name"]

            # UniFi's idea of a client's IP is not always current: the "ip" of a
            # connected client can briefly show an address the camera used
            # before, and "last_ip" can be stale for days. Try the reservation
            # first, then the address that answered last time, then the rest.
            candidates: list[str] = []
            for ip in (
                rec.get("fixed_ip") if rec.get("use_fixedip") else None,
                cam.last_good_ip,
                (conn or {}).get("ip"),
                rec.get("last_ip"),
            ):
                if ip and ip not in candidates:
                    candidates.append(ip)

            cam.reachable, details = False, []
            for i, ip in enumerate(candidates):
                ok, detail = await self.hass.async_add_executor_job(
                    _probe, ip, port, timeout, attempts if i == 0 else 1
                )
                details.append(f"{ip}: {detail}")
                if ok:
                    cam.reachable, cam.ip, cam.last_good_ip = True, ip, ip
                    break
            if not cam.reachable:
                cam.ip = candidates[0] if candidates else cam.ip
            detail = " | ".join(details) or "no IP address known"

            if cam.reachable:
                cam.state = STATE_OK
                cam.last_ok = now
                if cam.bad_since is not None:
                    _LOGGER.info("%s answers again after %s", cam.name, now - cam.bad_since)
                cam.bad_since = None
                cam.notified_this_outage = False
            else:
                cam.state = STATE_ZOMBIE if cam.associated else STATE_OFFLINE
                if cam.bad_since is None:
                    _LOGGER.info(
                        "%s does not answer on port %s (%s; %s)",
                        cam.name, port,
                        "on Wi-Fi" if cam.associated else "not on Wi-Fi", detail,
                    )
                else:
                    _LOGGER.debug("%s still silent: %s", cam.name, detail)
                cam.bad_since = cam.bad_since or now

        await asyncio.gather(*(check(c) for c in self.cameras.values()))

        if self.enabled:
            for cam in self.cameras.values():
                await self._maybe_act(cam, now)
        return dict(self.cameras)

    # ---- decisions -----------------------------------------------------
    def _roll_day(self, cam: CameraState, now: datetime) -> None:
        today = now.date().isoformat()
        if cam.action_day != today:
            cam.action_day = today
            cam.actions_today = 0

    async def _maybe_act(self, cam: CameraState, now: datetime) -> None:
        if cam.state == STATE_OK or cam.bad_since is None or cam.mac in self._busy:
            return
        threshold = timedelta(minutes=float(self._opt(CONF_THRESHOLD, DEFAULT_THRESHOLD)))
        if now - cam.bad_since < threshold:
            return
        self._roll_day(cam, now)
        cooldown = timedelta(minutes=float(self._opt(CONF_COOLDOWN, DEFAULT_COOLDOWN)))
        if cam.last_action_at and cam.last_action in (ACTION_KICK, ACTION_POWER_CYCLE) and now - cam.last_action_at < cooldown:
            return

        outage = int((now - cam.bad_since).total_seconds() // 60)
        capped = cam.actions_today >= int(self._opt(CONF_MAX_ACTIONS, DEFAULT_MAX_ACTIONS))
        switch = self._opt(CONF_POWER_SWITCHES, {}).get(cam.mac)

        if cam.state == STATE_ZOMBIE and self._opt(CONF_KICK_ENABLED, True) and not capped:
            await self.async_kick(cam, f"no answer on port {self._opt(CONF_PROBE_PORT, DEFAULT_PROBE_PORT)} for {outage} min while connected to Wi-Fi")
        elif cam.state == STATE_OFFLINE and switch and not capped:
            self._busy.add(cam.mac)
            self.hass.async_create_task(
                self._power_cycle(cam, switch, f"not on Wi-Fi for {outage} min")
            )
        elif not cam.notified_this_outage:
            why = "daily action limit reached" if capped else (
                "not on Wi-Fi and no power switch selected" if cam.state == STATE_OFFLINE else "kicking is turned off"
            )
            await self._record(cam, ACTION_NOTIFY_ONLY, f"down for {outage} min, {why}", count=False)
            cam.notified_this_outage = True

    # ---- actions -------------------------------------------------------
    async def async_kick(self, cam: CameraState, reason: str, manual: bool = False) -> None:
        """Kick the camera off Wi-Fi so it reconnects."""
        try:
            await self.client.kick(cam.mac)
        except UniFiError as err:
            _LOGGER.warning("Could not kick %s: %s", cam.name, err)
            return
        await self._record(cam, ACTION_KICK, ("manuellt: " if manual else "") + reason)

    async def _power_cycle(self, cam: CameraState, switch: str, reason: str) -> None:
        try:
            off_s = int(self._opt(CONF_POWER_OFF_SECONDS, DEFAULT_POWER_OFF_SECONDS))
            await self.hass.services.async_call("homeassistant", "turn_off", {"entity_id": switch}, blocking=True)
            await asyncio.sleep(off_s)
            await self.hass.services.async_call("homeassistant", "turn_on", {"entity_id": switch}, blocking=True)
            await self._record(cam, ACTION_POWER_CYCLE, f"{reason}; power cut for {off_s} s via {switch}")
        except Exception as err:  # noqa: BLE001 - any service failure must not kill the watchdog
            _LOGGER.warning("Power cycle of %s via %s failed: %s", cam.name, switch, err)
        finally:
            self._busy.discard(cam.mac)

    async def _record(self, cam: CameraState, action: str, reason: str, count: bool = True) -> None:
        now = dt_util.now()
        self._roll_day(cam, now)
        cam.last_action, cam.last_action_at, cam.last_action_reason = action, now, reason
        if count:
            cam.actions_today += 1
            cam.actions_total += 1
        _LOGGER.warning("%s: %s (%s)", cam.name, action, reason)
        self.hass.bus.async_fire(
            EVENT_ACTION,
            {"camera": cam.name, "mac": cam.mac, "ip": cam.ip, "action": action, "reason": reason},
        )
        if service := self._opt(CONF_NOTIFY_SERVICE, ""):
            domain, _, name = service.partition(".")
            text = {
                ACTION_KICK: "was kicked off Wi-Fi",
                ACTION_POWER_CYCLE: "was power cycled",
                ACTION_NOTIFY_ONLY: "is down",
            }[action]
            try:
                await self.hass.services.async_call(
                    domain,
                    name,
                    {"title": "UniFi Tapo Watchdog", "message": f"{cam.name} {text}: {reason}"},
                    blocking=False,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Notify via %s failed: %s", service, err)
        self.async_update_listeners()
