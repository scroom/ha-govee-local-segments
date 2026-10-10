"""Color helpers for segment gradients."""

from collections.abc import Sequence
import re
from typing import Any

import voluptuous as vol

RGB = tuple[int, int, int]

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _parse_one(value: Any) -> RGB:
    """Parse a single color given as hex string or [r, g, b]."""
    if isinstance(value, str):
        match = _HEX.match(value.strip())
        if not match:
            raise vol.Invalid(f"Invalid color '{value}', expected e.g. '#006a6a'")
        raw = bytes.fromhex(match.group(1))
        return (raw[0], raw[1], raw[2])
    if isinstance(value, Sequence) and len(value) == 3:
        try:
            rgb = tuple(int(c) for c in value)
        except (TypeError, ValueError) as err:
            raise vol.Invalid(f"Invalid color {value!r}") from err
        if all(0 <= c <= 255 for c in rgb):
            return rgb  # type: ignore[return-value]
    raise vol.Invalid(f"Invalid color {value!r}, expected hex or [r, g, b]")


def parse_colors(value: Any) -> list[RGB]:
    """Parse a list of colors.

    Accepts a list (hex strings and/or [r, g, b] triples) or a single string
    with hex colors separated by spaces or commas.
    """
    if isinstance(value, str):
        value = [part for part in re.split(r"[\s,;]+", value) if part]
    if not isinstance(value, list) or not value:
        raise vol.Invalid("At least one color is required")
    if all(isinstance(c, int) for c in value) and len(value) == 3:
        # A single [r, g, b] triple was given
        value = [value]
    return [_parse_one(c) for c in value]


def interpolate(colors: Sequence[RGB], count: int) -> list[RGB]:
    """Spread the given color stops evenly over ``count`` segments."""
    if count <= 0:
        return []
    if len(colors) == 1 or count == 1:
        return [tuple(colors[0])] * count  # type: ignore[list-item]
    result: list[RGB] = []
    stops = len(colors) - 1
    for i in range(count):
        pos = i / (count - 1) * stops
        k = min(int(pos), stops - 1)
        frac = pos - k
        a, b = colors[k], colors[k + 1]
        result.append(
            (
                round(a[0] + (b[0] - a[0]) * frac),
                round(a[1] + (b[1] - a[1]) * frac),
                round(a[2] + (b[2] - a[2]) * frac),
            )
        )
    return result


def scale(rgb: RGB, brightness: int) -> RGB:
    """Scale an RGB color by a brightness value 0..255."""
    return (
        round(rgb[0] * brightness / 255),
        round(rgb[1] * brightness / 255),
        round(rgb[2] * brightness / 255),
    )
