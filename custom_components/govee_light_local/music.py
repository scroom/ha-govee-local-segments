"""Music modes using the light's built-in microphone (ptReal over LAN).

Commands were taken from a decrypted Bluetooth capture of the Govee app
(H6076, app setting "from device") and replayed over the LAN API:

    33 05 0f <effect> <sensitivity 0-99> <flag> [extra]          simple effects
    a3 00 01 02 41 <effect> 07 <7 RGB colours …>                 palette, part 1
    a3 ff <rest of palette> [extra]                              palette, part 2
    then 33 05 0f <effect> <sensitivity> 00

Only models where this was verified on hardware are listed.
"""

from dataclasses import dataclass

MUSIC_MODELS: frozenset[str] = frozenset({"H6076"})

DEFAULT_SENSITIVITY = 99
_RAINBOW = bytes.fromhex("ff0000ff7f00ffff0000ff000000ff00ffff8b00ff")


@dataclass(frozen=True)
class MusicEffect:
    code: int
    flag: int = 0x00
    extra: bytes = b""
    palette: bool = False
    palette_extra: bytes = b""


MUSIC_EFFECTS: dict[str, MusicEffect] = {
    "music_energetic": MusicEffect(0x00, 0x01, bytes.fromhex("ff0000")),
    "music_rhythm": MusicEffect(0x04, 0x01),
    "music_bounce": MusicEffect(0x08),
    "music_hopping": MusicEffect(0x02),
    "music_beat": MusicEffect(0x06),
    "music_spray": MusicEffect(0x07),
    "music_skittles": MusicEffect(0x4D, palette=True),
    "music_torch": MusicEffect(0x50, palette=True),
    "music_candy_crush": MusicEffect(0x4E, palette=True),
    "music_fusion": MusicEffect(0x4F, palette=True),
    "music_shiny": MusicEffect(0x51, palette=True),
    "music_separation": MusicEffect(
        0x32, palette=True, palette_extra=bytes.fromhex("020061")
    ),
}


def supports_music(sku: str) -> bool:
    """Return True if music modes are verified for this model."""
    return sku in MUSIC_MODELS


def _frame(data: bytes) -> str:
    data = data + bytes(19 - len(data))
    checksum = 0
    for byte in data:
        checksum ^= byte
    return (data + bytes([checksum])).hex()


def music_packets(effect: str, sensitivity: int) -> list[list[str]]:
    """Return groups of 20-byte ptReal frames (hex) to send in order."""
    spec = MUSIC_EFFECTS[effect]
    sensitivity = max(0, min(99, int(sensitivity)))
    groups: list[list[str]] = []
    if spec.palette:
        payload = (
            bytes([0x01, 0x02, 0x41, spec.code, 0x07]) + _RAINBOW + spec.palette_extra
        )
        groups.append(
            [_frame(b"\xa3\x00" + payload[:17]), _frame(b"\xa3\xff" + payload[17:])]
        )
    groups.append(
        [
            _frame(
                bytes([0x33, 0x05, 0x0F, spec.code, sensitivity, spec.flag])
                + spec.extra
            )
        ]
    )
    return groups
