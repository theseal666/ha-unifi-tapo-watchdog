"""Config and options flow for UniFi Tapo Watchdog."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers import selector

from .api import UniFiAuthError, UniFiClient, UniFiError
from .const import (
    CONF_CAMERAS,
    CONF_COOLDOWN,
    CONF_HOST,
    CONF_KICK_ENABLED,
    CONF_MAX_ACTIONS,
    CONF_NOTIFY_SERVICE,
    CONF_POWER_OFF_SECONDS,
    CONF_POWER_SWITCHES,
    CONF_PROBE_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SITE,
    CONF_THRESHOLD,
    CONF_VERIFY_SSL,
    DEFAULT_COOLDOWN,
    DEFAULT_MAX_ACTIONS,
    DEFAULT_POWER_OFF_SECONDS,
    DEFAULT_PROBE_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SITE,
    DEFAULT_THRESHOLD,
    DOMAIN,
    TPLINK_OUIS,
)


def make_client(hass: HomeAssistant, data: dict[str, Any]) -> UniFiClient:
    """Client with its own cookie jar (UniFi OS keeps the session in a cookie)."""
    session = async_create_clientsession(
        hass,
        verify_ssl=data.get(CONF_VERIFY_SSL, False),
        cookie_jar=aiohttp.CookieJar(unsafe=True),
    )
    return UniFiClient(
        session,
        data[CONF_HOST],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data.get(CONF_SITE, DEFAULT_SITE),
        data.get(CONF_VERIFY_SSL, False),
    )


async def _camera_choices(client: UniFiClient) -> tuple[list[dict[str, str]], list[str], dict[str, str]]:
    """Options for the camera picker, the TP-Link ones to preselect, and MAC->name."""
    connected = await client.connected_clients()
    known = await client.known_clients()
    names: dict[str, str] = {}
    choices: list[dict[str, str]] = []
    suggested: list[str] = []
    for mac in sorted(set(known) | set(connected)):
        rec = {**known.get(mac, {}), **connected.get(mac, {})}
        if rec.get("is_wired"):
            continue
        name = rec.get("name") or rec.get("hostname") or mac
        ip = rec.get("ip") or rec.get("fixed_ip") or rec.get("last_ip") or "?"
        tplink = mac[:8] in TPLINK_OUIS or "tapo" in name.lower()
        if not (tplink or mac in connected):
            continue
        names[mac] = name
        choices.append({"value": mac, "label": f"{name} ({ip}, {mac})"})
        if tplink:
            suggested.append(mac)
    choices.sort(key=lambda c: (c["value"] not in suggested, c["label"].lower()))
    return choices, suggested, names


def _settings_schema(opts: dict[str, Any]) -> dict[Any, Any]:
    num = lambda lo, hi, unit: selector.NumberSelector(  # noqa: E731
        selector.NumberSelectorConfig(min=lo, max=hi, step=1, unit_of_measurement=unit, mode=selector.NumberSelectorMode.BOX)
    )
    return {
        vol.Required(CONF_SCAN_INTERVAL, default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): num(20, 600, "s"),
        vol.Required(CONF_THRESHOLD, default=opts.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)): num(1, 120, "min"),
        vol.Required(CONF_COOLDOWN, default=opts.get(CONF_COOLDOWN, DEFAULT_COOLDOWN)): num(1, 1440, "min"),
        vol.Required(CONF_MAX_ACTIONS, default=opts.get(CONF_MAX_ACTIONS, DEFAULT_MAX_ACTIONS)): num(1, 100, None),
        vol.Required(CONF_PROBE_PORT, default=opts.get(CONF_PROBE_PORT, DEFAULT_PROBE_PORT)): num(1, 65535, None),
        vol.Required(CONF_KICK_ENABLED, default=opts.get(CONF_KICK_ENABLED, True)): selector.BooleanSelector(),
        vol.Required(CONF_POWER_OFF_SECONDS, default=opts.get(CONF_POWER_OFF_SECONDS, DEFAULT_POWER_OFF_SECONDS)): num(3, 120, "s"),
        vol.Optional(CONF_NOTIFY_SERVICE, description={"suggested_value": opts.get(CONF_NOTIFY_SERVICE, "")}): selector.TextSelector(),
    }


class WatchdogConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the watchdog: UniFi login first, then which cameras to watch."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._names: dict[str, str] = {}
        self._choices: list[dict[str, str]] = []
        self._suggested: list[str] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = make_client(self.hass, user_input)
            try:
                await client.login()
                self._choices, self._suggested, self._names = await _camera_choices(client)
            except UniFiAuthError:
                errors["base"] = "invalid_auth"
            except UniFiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{user_input[CONF_HOST]}_{user_input.get(CONF_SITE, DEFAULT_SITE)}")
                self._abort_if_unique_id_configured()
                self._data = user_input
                return await self.async_step_cameras()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default="192.168.0.1"): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                    vol.Required(CONF_SITE, default=DEFAULT_SITE): str,
                    vol.Required(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_cameras(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            macs = user_input[CONF_CAMERAS]
            options = {
                CONF_CAMERAS: {m: self._names.get(m, m) for m in macs},
                **{k: v for k, v in user_input.items() if k != CONF_CAMERAS},
            }
            return self.async_create_entry(title="UniFi Tapo Watchdog", data=self._data, options=options)

        schema = {
            vol.Required(CONF_CAMERAS, default=self._suggested): selector.SelectSelector(
                selector.SelectSelectorConfig(options=self._choices, multiple=True, mode=selector.SelectSelectorMode.LIST)
            ),
            **_settings_schema({}),
        }
        return self.async_show_form(step_id="cameras", data_schema=vol.Schema(schema))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return WatchdogOptionsFlow()


class WatchdogOptionsFlow(OptionsFlow):
    """Change cameras, timings and the optional power switches."""

    def __init__(self) -> None:
        self._new: dict[str, Any] = {}
        self._names: dict[str, str] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        opts = self.config_entry.options
        client = make_client(self.hass, self.config_entry.data)
        try:
            choices, _, self._names = await _camera_choices(client)
        except UniFiError:
            return self.async_abort(reason="cannot_connect")
        current = list(opts.get(CONF_CAMERAS, {}))
        # Keep cameras that are configured but currently unknown/offline selectable.
        for mac in current:
            if mac not in {c["value"] for c in choices}:
                choices.append({"value": mac, "label": f"{opts[CONF_CAMERAS][mac]} ({mac}, syns inte nu)"})
                self._names[mac] = opts[CONF_CAMERAS][mac]

        if user_input is not None:
            self._new = {
                **user_input,
                CONF_CAMERAS: {m: self._names.get(m, m) for m in user_input[CONF_CAMERAS]},
            }
            return await self.async_step_power()

        schema = {
            vol.Required(CONF_CAMERAS, default=current): selector.SelectSelector(
                selector.SelectSelectorConfig(options=choices, multiple=True, mode=selector.SelectSelectorMode.LIST)
            ),
            **_settings_schema(dict(opts)),
        }
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))

    async def async_step_power(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Optional: a switch per camera that cuts its power when it is not on Wi-Fi."""
        cams: dict[str, str] = self._new[CONF_CAMERAS]
        current = self.config_entry.options.get(CONF_POWER_SWITCHES, {})
        # The form field is labelled with the camera's name; map it back to the MAC.
        label = {mac: f"{name} ({mac})" for mac, name in cams.items()}
        if user_input is not None:
            switches = {mac: user_input[label[mac]] for mac in cams if user_input.get(label[mac])}
            return self.async_create_entry(data={**self._new, CONF_POWER_SWITCHES: switches})

        schema = {
            vol.Optional(label[mac], description={"suggested_value": current.get(mac)}): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "light"])
            )
            for mac in cams
        }
        return self.async_show_form(step_id="power", data_schema=vol.Schema(schema))
