"""Constants for UniFi Tapo Watchdog."""

from __future__ import annotations

DOMAIN = "unifi_tapo_watchdog"

CONF_HOST = "host"
CONF_SITE = "site"
CONF_VERIFY_SSL = "verify_ssl"

CONF_CAMERAS = "cameras"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_THRESHOLD = "threshold_minutes"
CONF_COOLDOWN = "cooldown_minutes"
CONF_MAX_ACTIONS = "max_actions_per_day"
CONF_PROBE_PORT = "probe_port"
CONF_PROBE_TIMEOUT = "probe_timeout"
CONF_PROBE_ATTEMPTS = "probe_attempts"
CONF_KICK_ENABLED = "kick_enabled"
CONF_POWER_SWITCHES = "power_switches"
CONF_POWER_OFF_SECONDS = "power_off_seconds"
CONF_NOTIFY_SERVICE = "notify_service"

DEFAULT_SITE = "default"
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_THRESHOLD = 5
DEFAULT_COOLDOWN = 15
DEFAULT_MAX_ACTIONS = 6
DEFAULT_PROBE_PORT = 554
DEFAULT_POWER_OFF_SECONDS = 15

DEFAULT_PROBE_TIMEOUT = 5
DEFAULT_PROBE_ATTEMPTS = 2
PROBE_RETRY_DELAY = 2  # seconds between attempts

# Camera states
STATE_OK = "ok"
STATE_ZOMBIE = "zombie"  # on Wi-Fi according to UniFi, but does not answer
STATE_OFFLINE = "offline"  # not on Wi-Fi at all
STATE_UNKNOWN = "unknown"

# Actions
ACTION_KICK = "kick"
ACTION_POWER_CYCLE = "power_cycle"
ACTION_NOTIFY_ONLY = "notify_only"

EVENT_ACTION = f"{DOMAIN}_action"

# MAC prefixes (OUIs) used by TP-Link / Tapo cameras; used to suggest cameras in the setup.
TPLINK_OUIS = (
    "8c:86:dd",
    "3c:6a:d2",
    "7c:f1:7e",
    "10:5a:95",
    "0c:ef:15",
    "54:af:97",
    "5c:a6:e6",
    "1c:61:b4",
    "30:de:4b",
    "60:a4:b7",
    "98:da:c4",
    "b0:a7:b9",
    "c0:06:c3",
    "d8:07:b6",
    "f0:a7:31",
)
