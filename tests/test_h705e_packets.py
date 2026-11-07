"""H705E packet regressions from decrypted app commands."""

import base64
import json
from functools import reduce
from operator import xor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from govee_local_api.message import SegmentColorMessages

from custom_components.govee_light_local.segments import (
    h705e_segment_frame,
    segment_count,
    set_segment_rgb_color,
)

EVIDENCE = json.loads(
    (Path(__file__).parent / "fixtures" / "h705e_segment_colors.json").read_text()
)


@pytest.mark.parametrize("command", EVIDENCE["commands"])
def test_captured_command(command) -> None:
    """Match all 18 checksum-valid app writes, including non-primary colors."""
    assert (
        h705e_segment_frame(command["section"], tuple(command["rgb"])).hex()
        == command["frame"]
    )


@pytest.mark.parametrize("section", range(1, 16))
def test_legacy_packet_equivalence(section: int) -> None:
    rgb = (17, 85, 204)
    legacy = SegmentColorMessages((1 << (section - 1)).to_bytes(2, "little"), rgb)
    frame = base64.b64decode(legacy.as_dict()["msg"]["data"]["command"][0])
    assert h705e_segment_frame(section, rgb) == frame


@pytest.mark.parametrize("section", range(1, 22))
def test_black_packet(section: int) -> None:
    frame = h705e_segment_frame(section, (0, 0, 0))
    assert len(frame) == 20
    assert frame[4:7] == bytes(3)
    assert reduce(xor, frame, 0) == 0


@pytest.mark.parametrize("section", [0, 22, -1, True, 1.0])
def test_invalid_section(section) -> None:
    with pytest.raises(ValueError):
        h705e_segment_frame(section, (255, 0, 0))


@pytest.mark.parametrize("rgb", [(256, 0, 0), (0, -1, 0), (1, 2), (True, 0, 0)])
def test_invalid_rgb(rgb) -> None:
    with pytest.raises(ValueError):
        h705e_segment_frame(21, rgb)


@pytest.mark.parametrize(("sku", "section"), [("H705E", 15), ("H6076", 7)])
async def test_legacy_routing(sku: str, section: int) -> None:
    device = SimpleNamespace(
        sku=sku, send_raw_command=AsyncMock(), set_segment_rgb_color=AsyncMock()
    )
    await set_segment_rgb_color(device, section, 255, 0, 0)
    device.set_segment_rgb_color.assert_awaited_once_with(section, 255, 0, 0)
    device.send_raw_command.assert_not_awaited()


async def test_extended_routing() -> None:
    device = SimpleNamespace(
        sku="H705E", send_raw_command=AsyncMock(), set_segment_rgb_color=AsyncMock()
    )
    await set_segment_rgb_color(device, 21, 255, 0, 0)
    device.send_raw_command.assert_awaited_once_with(
        "33051501ff0000000000000000001000000000cd"
    )
    device.set_segment_rgb_color.assert_not_awaited()


@pytest.mark.parametrize(("sku", "expected"), [("H705E", 21), ("H705F", 15)])
def test_model_specific_count(sku: str, expected: int) -> None:
    device = SimpleNamespace(sku=sku, capabilities=SimpleNamespace(segments_count=15))
    assert segment_count(device) == expected
