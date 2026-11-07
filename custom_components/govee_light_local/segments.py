"""Model-specific segment addressing observed in an H705E Bluetooth capture.

H705E sections 16–21 use bits 15–20 of the little-endian mask at bytes
12–18 of a 19-byte payload. The BLE capture contains valid XOR checksums.
Section 21 was also physically verified over LAN on the capture device.
"""

from __future__ import annotations

from functools import reduce
from operator import xor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from govee_local_api import GoveeDevice


def segment_count(device: GoveeDevice) -> int:
    """Use the capture-backed count only for H705E."""
    if device.sku == "H705E":
        return 21
    return device.capabilities.segments_count


def h705e_segment_frame(segment: int, rgb: tuple[int, int, int]) -> bytes:
    """Build a complete 20-byte color frame, including its XOR checksum."""
    if type(segment) is not int or not 1 <= segment <= 21:
        raise ValueError("H705E segment must be an integer from 1 to 21")
    if len(rgb) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in rgb):
        raise ValueError("RGB must contain three integers from 0 to 255")
    payload = (
        bytes.fromhex("33 05 15 01")
        + bytes(rgb)
        + bytes(5)
        + (1 << (segment - 1)).to_bytes(7, "little")
    )
    return payload + bytes([reduce(xor, payload, 0)])


async def set_segment_rgb_color(
    device: GoveeDevice, segment: int, red: int, green: int, blue: int
) -> None:
    """Keep the original path for supported segments and other models."""
    if device.sku == "H705E" and segment > 15:
        frame = h705e_segment_frame(segment, (red, green, blue))
        # send_raw_command expects hex WITH a checksum (HexMessage does not add one).
        await device.send_raw_command(frame.hex())
    else:
        await device.set_segment_rgb_color(segment, red, green, blue)
