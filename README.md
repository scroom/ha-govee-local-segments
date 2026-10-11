# Govee lights local – segment control (proof of concept)

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=scroom&repository=ha-govee-local-segments&category=integration)

A fork of Home Assistant's built-in **Govee lights local** integration
(`govee_light_local`, taken from HA 2026.10.1) that exposes the
**segment control already implemented in the underlying library**
[`govee-local-api`](https://github.com/Galorhallen/govee-local-api) 3.1.0.

Everything stays local (LAN API, UDP). No Govee account, API key or cloud.

## What it adds

| | |
|---|---|
| **Segment lights** | One RGB light entity per segment (`light.<lamp>_segment_1` …), attached to the same device. Brightness is emulated by scaling RGB. |
| **`govee_light_local.set_gradient`** | Spreads two or more color stops evenly over all segments (first color = segment 1). Options: `brightness_pct`, `reverse`. |
| **Music modes** | H6076: the 12 music effects of the Govee app (built-in microphone, "from device") as `Music: …` effects, plus a **Music sensitivity** number. Commands taken from a decrypted BLE capture of the app (`33 05 0f …`, palette frames `a3 …`) and verified over LAN. |
| **State sync** | Whole-lamp changes (RGB, color temperature, scene, on/off) are mirrored on the segment entities. |

Segment colors cannot be read back from the device, so segment state is
**optimistic** (what HA last sent) and restored after a restart.
Everything else behaves exactly like the core integration; the original core
test suite passes unchanged against this fork.

## Verified hardware

| Model | Segments | Segment 1 | Tested |
|---|---|---|---|
| H6076 (RGBICWW floor lamp) | 7 | bottom | HA 2026.10.0, LAN only (internet blocked): single segments, brightness, segment off, gradients (2/3 stops, reverse, area target), sync with main light (RGB, color temp, scene, on/off), state restore after restart, all 12 music effects and music sensitivity |

Segment counts come from `govee-local-api`'s capability table. Reports for
other models are welcome.

## Installation

Requires Home Assistant **2026.10** or newer.

1. **HACS:** click the button above (opens HACS in your Home Assistant),
   or HACS → ⋮ → *Custom repositories* → add
   `https://github.com/scroom/ha-govee-local-segments` (type *Integration*), then download it.
   **Manual:** copy `custom_components/govee_light_local` to `/config/custom_components/`.
2. Restart Home Assistant. A warning that a custom integration overrides a
   core integration is expected. Existing config entries and entity IDs are kept.
3. To go back: delete the folder, restart, remove the orphaned segment entities.

## Example

```yaml
action: govee_light_local.set_gradient
target:
  entity_id: light.h6076
data:
  colors: ["#006a6a", "#0040ff"]   # or "006a6a 0040ff" or [[0,106,106],[0,64,255]]
  brightness_pct: 60
```

## Development

```bash
pip install pytest-homeassistant-custom-component govee-local-api==3.1.0
pytest tests tests_core
```

`tests/` covers the new features, `tests_core/` is the unmodified core test
suite pointed at this fork.

## How the music commands were found

The Govee app talks to the H6076 over Bluetooth with the vendor's "version 1"
encryption (AES-ECB plus RC4 for the last bytes, session key from a handshake
that is encrypted with an app-wide constant). That scheme is documented in
[teh-hippo/ha-govee-led-ble](https://github.com/teh-hippo/ha-govee-led-ble).
With it, an Android HCI snoop log of the app could be decrypted. The plaintext
commands were then sent unchanged over the LAN API (`ptReal`), which needs no
encryption. No keys are shipped in this integration.

Music command layout on the H6076:

```
33 05 0f <effect> <sensitivity 0-99> <flag> [extra]         simple effects
a3 00 01 02 41 <effect> 07 <7 RGB colours …>                palette, part 1
a3 ff <rest of palette> [extra]                             palette, part 2
```

| Effect (app) | Code | | Effect (app) | Code |
|---|---|---|---|---|
| Energetic | 0x00 | | Skittles | 0x4D (palette) |
| Rhythm | 0x04 | | Torch | 0x50 (palette) |
| Bounce | 0x08 | | Candy Crush | 0x4E (palette) |
| Hopping | 0x02 | | Fusion | 0x4F (palette) |
| Beat | 0x06 | | Shiny | 0x51 (palette) |
| Spray | 0x07 | | Separation | 0x32 (palette) |

## Goal

This is meant as a proof of concept for upstreaming segment support into the
core integration, not as a long-term separate integration.

## Credits

Based on the `govee_light_local` integration of
[Home Assistant](https://github.com/home-assistant/core) and the library
[govee-local-api](https://github.com/Galorhallen/govee-local-api) by
@Galorhallen. All protocol work for segments is theirs; this fork only exposes
it in Home Assistant. The BLE decryption approach used to find the music
commands comes from [teh-hippo/ha-govee-led-ble](https://github.com/teh-hippo/ha-govee-led-ble).

License: Apache 2.0 (same as Home Assistant).
