# Govee lights local – segment control (proof of concept)

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
| **State sync** | Whole-lamp changes (RGB, color temperature, scene, on/off) are mirrored on the segment entities. |

Segment colors cannot be read back from the device, so segment state is
**optimistic** (what HA last sent) and restored after a restart.
Everything else behaves exactly like the core integration; the original core
test suite passes unchanged against this fork.

## Verified hardware

| Model | Segments | Segment 1 | Tested |
|---|---|---|---|
| H6076 (RGBICWW floor lamp) | 7 | bottom | HA 2026.10.0, LAN only (internet blocked): single segments, brightness, segment off, gradients (2/3 stops, reverse, area target), sync with main light (RGB, color temp, scene, on/off), state restore after restart |

Segment counts come from `govee-local-api`'s capability table. Reports for
other models are welcome.

## Installation

Requires Home Assistant **2026.10** or newer.

1. **HACS:** HACS → ⋮ → *Custom repositories* → add
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

## Goal

This is meant as a proof of concept for upstreaming segment support into the
core integration, not as a long-term separate integration.

## Credits

Based on the `govee_light_local` integration of
[Home Assistant](https://github.com/home-assistant/core) and the library
[govee-local-api](https://github.com/Galorhallen/govee-local-api) by
@Galorhallen. All protocol work for segments is theirs; this fork only exposes
it in Home Assistant.

License: Apache 2.0 (same as Home Assistant).
