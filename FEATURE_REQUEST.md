<!--
Where to post:
  New discussion at https://github.com/orgs/home-assistant/discussions
  Category: "Integration enhancements", label: integration: govee_light_local
  Then leave a short comment with a link in discussion #2167 (H6076 scenes).
-->

# Govee lights local: expose segment control (library support exists, PoC available)

cc @Galorhallen (codeowner of `govee_light_local` and author of `govee-local-api`)

## Summary

`govee-local-api` 3.1.0 (the library behind `govee_light_local`) already
implements per-segment RGB control over the LAN API
(`GoveeDevice.set_segment_rgb_color`, `ptReal` / `33 05 15 01 …` packets) and
ships segment counts for many RGBIC models. The Home Assistant integration
does not expose it yet: there are no segment entities and no action.

I'd like to propose exposing it and offer a working proof of concept as a
starting point.

## Verified on hardware

Govee **H6076** floor lamp, LAN API enabled, no cloud connection:

- The library's segment packet (`MwUVAQAA/wAAAAAAAQAAAAAAANw=`, segment 1 blue)
  sent to UDP 4003 colors exactly one segment.
- Walking the bitmask shows **7 segments**, segment 1 at the **bottom**,
  which matches the library's capability entry for H6076.

## Proof of concept

https://github.com/scroom/ha-govee-local-segments – a fork of the core integration from 2026.10.1 with:

1. **Segment light entities** – one RGB light per segment, attached to the
   same device, unique ID `<fingerprint>_segment_<n>`, name via translation
   placeholder ("Segment 1"). Brightness is emulated by scaling RGB.
   State is optimistic (the device does not report segment colors) and
   restored with `RestoreEntity`. Whole-lamp changes are mirrored on the
   segments (RGB → same color, color temperature/scene → color unknown,
   on/off → follows the lamp).
2. **Entity action `govee_light_local.set_gradient`** – spreads a list of
   color stops evenly over the segments (optional `brightness_pct`, `reverse`).

Tests: new tests for segments and the action, plus the unmodified core test
suite of `govee_light_local`, all passing against HA 2026.10.

Verified on the real H6076 (HA 2026.10.0, lamp blocked from the internet):
single segments (color, brightness, off), gradients with two and three stops,
`reverse`, area target, mirroring of whole-lamp changes (RGB, color
temperature, scene, on/off) and state restore after a restart. No segment
commands were dropped with the 50 ms pause.

## Questions for the maintainers

1. Are segment light entities acceptable here (similar to WLED), and should
   they be **disabled by default**? In the PoC they are enabled.
2. Is an entity action like `set_gradient` acceptable, or should gradients be
   left to scripts/blueprints that drive the segment entities?
3. Library side: would a multi-packet send (all segments in one `ptReal`
   message) be welcome? The PoC uses the public per-segment call with a 50 ms
   pause between commands.

If this direction is fine, I'm happy to turn the PoC into a PR (core and, if
useful, the library).

Related: https://github.com/orgs/home-assistant/discussions/2167 (scenes for H6076).
