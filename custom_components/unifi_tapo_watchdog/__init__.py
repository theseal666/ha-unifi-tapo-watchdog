"""UniFi Tapo Watchdog: notices when a Wi-Fi camera hangs and gets it back."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .api import UniFiAuthError, UniFiError
from .config_flow import make_client
from .const import DOMAIN
from .coordinator import WatchdogCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH, Platform.BUTTON]

WatchdogConfigEntry = ConfigEntry[WatchdogCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: WatchdogConfigEntry) -> bool:
    client = make_client(hass, entry.data)
    try:
        await client.login()
    except UniFiAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except UniFiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = WatchdogCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="UniFi Tapo Watchdog",
        manufacturer="UniFi Tapo Watchdog",
        model="Vakt",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: WatchdogConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: WatchdogConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
