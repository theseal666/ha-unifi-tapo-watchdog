# UniFi Tapo Watchdog

Wi-Fi cameras such as the TP-Link Tapo C200 sometimes hang: they stay connected
to Wi-Fi, but stop answering — no RTSP, no ping — until they are restarted. On a
UniFi network the cure is usually to disconnect the camera from Wi-Fi so it
reconnects. This integration does that for you.

Every minute it asks your UniFi console which clients are connected and tries to
open the camera's RTSP port. When a camera has been silent for a few minutes it
acts:

| The camera is… | The watchdog… |
|---|---|
| on Wi-Fi but silent | kicks it off Wi-Fi so it reconnects |
| not on Wi-Fi at all | cuts its power for a moment, if you picked a switch for it — otherwise it only notifies you |

A cooldown and a daily cap stop it from kicking a camera in a loop.

## Requirements

- A UniFi OS console: Cloud Gateway (UCG), Dream Machine (UDM) or Dream Router (UDR).
- A local UniFi account with admin rights in the Network application.
- Home Assistant must be able to reach the cameras' RTSP port (554) — across VLANs too.

## Installation

### HACS

1. HACS → ⋮ → **Custom repositories** → add this repository as an *Integration*.
2. Install **UniFi Tapo Watchdog** and restart Home Assistant.

### Manual

Copy `custom_components/unifi_tapo_watchdog` into your `config/custom_components`
folder and restart Home Assistant.

## Setup

**Settings → Devices & services → Add integration → UniFi Tapo Watchdog.**

1. Enter the console address (for example `192.168.0.1`) and the local account.
2. Pick the cameras. TP-Link/Tapo devices are preselected.

## Settings

All settings can be changed later under **Configure**.

| Setting | Default | |
|---|---|---|
| Check interval | 60 s | How often the cameras are checked |
| Minutes down before acting | 5 min | How long a camera must be silent before the watchdog acts |
| Minutes between actions | 15 min | Cooldown per camera |
| Max actions per day | 6 | Per camera; after that you only get a notification |
| Port to probe | 554 | RTSP. Use 443 or another port for cameras without RTSP |
| Kick a silent camera off Wi-Fi | on | Turn off to only watch and notify |
| Seconds without power | 15 s | Used when power cycling through a switch |
| Notify service | — | For example `notify.mobile_app_phone` |
| Power switches | — | Optional, one per camera: a smart plug the camera is powered through |

## Entities

Per camera:

- **Reachable** — on when the camera answers. Attributes: IP, Wi-Fi state, access point, signal, down since.
- **Status** — `ok`, `zombie` (on Wi-Fi but silent) or `offline` (not on Wi-Fi).
- **Last action** — when the watchdog last acted, with the action and the reason as attributes.
- **Actions today** — kicks and power cycles today.
- **Kick off Wi-Fi** — button.

For the watchdog: **Watchdog active** (switch — when off, it only watches) and **Cameras down**.

## Events

Every action fires `unifi_tapo_watchdog_action`:

```yaml
camera: TAPO Nere
mac: 3c:6a:d2:dc:c0:0d
ip: 192.168.30.51
action: kick          # kick | power_cycle | notify_only
reason: "svarar inte på port 554 sedan 5 min men är ansluten till WiFi"
```

## Tips for Tapo cameras

- Turn on **Auto reboot** in the Tapo app (for example at 03:00). The watchdog
  covers the hours in between.
- Keep the number of things that connect to the camera low: let one go2rtc
  instance read the camera and have Frigate, Scrypted and the rest read from
  go2rtc.
- ONVIF adds a connection of its own. Leave it off if you do not use pan/tilt.

## License

MIT — see [LICENSE](LICENSE).
