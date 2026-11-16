# Brand assets

| File | Size | Purpose |
|---|---|---|
| `icon.svg` | vector | Source — edit this, then regenerate the PNGs |
| `icon.png` | 256×256 | What Home Assistant loads |
| `icon@2x.png` | 512×512 | High-DPI variant |

Home Assistant 2026.3 and newer serve these from the integration's own `brand/`
folder; nothing needs to go into `manifest.json`.

The mark is a camera with a reconnect badge — the watchdog's job is to get a
hung camera back on the network. Home Assistant blue (`#41BDF5`) on white.

Regenerate:

```sh
convert -background none -density 288 icon.svg -resize 256x256 PNG32:icon.png
convert -background none -density 576 icon.svg -resize 512x512 PNG32:icon@2x.png
```
