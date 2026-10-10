"""Tests for segment lights and the set_gradient action."""

import base64
from unittest.mock import AsyncMock, call

from govee_local_api.light_capabilities import BASIC_CAPABILITIES
from govee_local_api.message import SegmentColorMessages
import pytest
from pytest_homeassistant_custom_component.common import mock_restore_cache

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import DOMAIN, setup_light

MAIN = "light.h6076"
SEG = "light.h6076_segment_{}"


def segment_calls(mock_govee_api: AsyncMock) -> list[tuple[int, tuple[int, int, int]]]:
    """Return (segment, rgb) for every segment command sent."""
    return [
        (c.args[1], tuple(c.args[2]))
        for c in mock_govee_api.set_segment_rgb_color.call_args_list
    ]


def test_packet_matches_hardware_test() -> None:
    """The library builds exactly the packet that worked on the real H6076."""
    msg = SegmentColorMessages(b"\x01\x00", (0, 0, 255))
    assert msg.as_dict()["msg"]["data"]["command"] == ["MwUVAQAA/wAAAAAAAQAAAAAAANw="]
    raw = base64.b64decode("MwUVAQAA/wAAAAAAAQAAAAAAANw=")
    assert len(raw) == 20


async def test_entities_created(hass: HomeAssistant, mock_govee_api) -> None:
    """H6076 gets one main light and seven segment lights."""
    await setup_light(hass, mock_govee_api)
    assert hass.states.get(MAIN) is not None
    for i in range(1, 8):
        assert hass.states.get(SEG.format(i)) is not None
    assert hass.states.get(SEG.format(8)) is None
    entry = er.async_get(hass).async_get(SEG.format(1))
    assert entry.unique_id == "AA:BB:CC:DD_segment_1"


async def test_no_segments_for_basic_device(
    hass: HomeAssistant, mock_govee_api
) -> None:
    """Devices without segment support get no segment entities."""
    await setup_light(hass, mock_govee_api, BASIC_CAPABILITIES, sku="H6008")
    assert len(hass.states.async_all()) == 1
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_gradient",
            {ATTR_ENTITY_ID: "light.h6008", "colors": ["#ff0000", "#0000ff"]},
            blocking=True,
        )


@pytest.mark.parametrize(
    "colors",
    [["#006a6a", "#0040ff"], "006a6a 0040ff", [[0, 106, 106], [0, 64, 255]]],
)
async def test_set_gradient(hass: HomeAssistant, mock_govee_api, colors) -> None:
    """A two-stop gradient is spread over the seven segments."""
    await setup_light(hass, mock_govee_api)
    await hass.services.async_call(
        DOMAIN,
        "set_gradient",
        {ATTR_ENTITY_ID: MAIN, "colors": colors, "brightness_pct": 60},
        blocking=True,
    )
    calls = segment_calls(mock_govee_api)
    assert [seg for seg, _ in calls] == [1, 2, 3, 4, 5, 6, 7]
    assert calls[0][1] == (0, 106, 106)
    assert calls[3][1] == (0, 85, 180)
    assert calls[6][1] == (0, 64, 255)
    mock_govee_api.set_brightness.assert_awaited_once()
    assert mock_govee_api.set_brightness.call_args.args[1] == 60

    assert hass.states.get(SEG.format(1)).attributes[ATTR_RGB_COLOR] == (0, 106, 106)
    assert hass.states.get(SEG.format(7)).attributes[ATTR_RGB_COLOR] == (0, 64, 255)


async def test_set_gradient_reverse_and_three_stops(
    hass: HomeAssistant, mock_govee_api
) -> None:
    """Three stops, reversed: last color ends up on segment 1."""
    await setup_light(hass, mock_govee_api)
    await hass.services.async_call(
        DOMAIN,
        "set_gradient",
        {
            ATTR_ENTITY_ID: MAIN,
            "colors": ["#ff0000", "#00ff00", "#0000ff"],
            "reverse": True,
        },
        blocking=True,
    )
    calls = segment_calls(mock_govee_api)
    assert calls[0] == (1, (0, 0, 255))
    assert calls[3] == (4, (0, 255, 0))
    assert calls[6] == (7, (255, 0, 0))
    mock_govee_api.set_brightness.assert_not_awaited()


async def test_invalid_color_rejected(hass: HomeAssistant, mock_govee_api) -> None:
    """Garbage colors are rejected before anything is sent."""
    await setup_light(hass, mock_govee_api)
    with pytest.raises(Exception, match="Invalid color"):
        await hass.services.async_call(
            DOMAIN,
            "set_gradient",
            {ATTR_ENTITY_ID: MAIN, "colors": ["petrol", "#0040ff"]},
            blocking=True,
        )
    mock_govee_api.set_segment_rgb_color.assert_not_awaited()


async def test_segment_on_off_brightness(hass: HomeAssistant, mock_govee_api) -> None:
    """Segment brightness is emulated by scaling the RGB value."""
    await setup_light(hass, mock_govee_api)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            ATTR_ENTITY_ID: SEG.format(3),
            ATTR_RGB_COLOR: (255, 128, 0),
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )
    assert segment_calls(mock_govee_api)[-1] == (3, (128, 64, 0))
    state = hass.states.get(SEG.format(3))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGB_COLOR] == (255, 128, 0)
    assert state.attributes[ATTR_BRIGHTNESS] == 128

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: SEG.format(3)}, blocking=True
    )
    assert segment_calls(mock_govee_api)[-1] == (3, (0, 0, 0))
    assert hass.states.get(SEG.format(3)).state == STATE_OFF
    # the lamp itself stays on
    mock_govee_api.turn_on_off.assert_not_awaited()
    assert hass.states.get(MAIN).state == STATE_ON


async def test_segment_turns_lamp_on(hass: HomeAssistant, mock_govee_api) -> None:
    """Switching a segment on while the lamp is off switches the lamp on first."""
    _, device = await setup_light(hass, mock_govee_api)
    device._is_on = False  # noqa: SLF001
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: SEG.format(1), ATTR_RGB_COLOR: (0, 0, 255)},
        blocking=True,
    )
    assert mock_govee_api.turn_on_off.call_args_list == [call(device, True)]
    assert segment_calls(mock_govee_api) == [(1, (0, 0, 255))]


async def test_main_light_updates_segments(hass: HomeAssistant, mock_govee_api) -> None:
    """Whole-lamp changes are mirrored on the segment entities."""
    await setup_light(hass, mock_govee_api)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: MAIN, ATTR_RGB_COLOR: (255, 0, 0)},
        blocking=True,
    )
    for i in range(1, 8):
        assert hass.states.get(SEG.format(i)).attributes[ATTR_RGB_COLOR] == (255, 0, 0)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: MAIN, ATTR_COLOR_TEMP_KELVIN: 4000},
        blocking=True,
    )
    assert hass.states.get(SEG.format(1)).attributes[ATTR_RGB_COLOR] is None

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: MAIN}, blocking=True
    )
    for i in range(1, 8):
        assert hass.states.get(SEG.format(i)).state == STATE_OFF


async def test_gradient_on_segment_is_ignored(
    hass: HomeAssistant, mock_govee_api
) -> None:
    """Targeting a segment does nothing (and does not fail)."""
    await setup_light(hass, mock_govee_api)
    await hass.services.async_call(
        DOMAIN,
        "set_gradient",
        {ATTR_ENTITY_ID: SEG.format(1), "colors": ["#ff0000", "#0000ff"]},
        blocking=True,
    )
    mock_govee_api.set_segment_rgb_color.assert_not_awaited()


async def test_gradient_on_whole_device(hass: HomeAssistant, mock_govee_api) -> None:
    """Targeting the device (main light + segments) applies the gradient once."""
    await setup_light(hass, mock_govee_api)
    device_id = er.async_get(hass).async_get(MAIN).device_id
    await hass.services.async_call(
        DOMAIN,
        "set_gradient",
        {"device_id": device_id, "colors": ["#ff0000", "#0000ff"]},
        blocking=True,
    )
    assert len(segment_calls(mock_govee_api)) == 7


async def test_restore_segment_state(hass: HomeAssistant, mock_govee_api) -> None:
    """Segment colors survive a restart (optimistic state)."""
    mock_restore_cache(
        hass,
        [
            State(
                SEG.format(2),
                STATE_ON,
                {ATTR_RGB_COLOR: (10, 20, 30), ATTR_BRIGHTNESS: 100},
            )
        ],
    )
    await setup_light(hass, mock_govee_api)
    state = hass.states.get(SEG.format(2))
    assert state.attributes[ATTR_RGB_COLOR] == (10, 20, 30)
    assert state.attributes[ATTR_BRIGHTNESS] == 100
