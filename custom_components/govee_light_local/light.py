"""Govee light local."""

import asyncio
import logging
from typing import Any, override

from govee_local_api import GoveeDevice, GoveeLightFeatures
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    filter_supported_color_modes,
)
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_COLORS,
    ATTR_REVERSE,
    DEVICE_TIMEOUT,
    DOMAIN,
    MANUFACTURER,
    SEGMENT_SEND_DELAY,
    SERVICE_SET_GRADIENT,
    SIGNAL_DEVICE_UPDATED,
    SIGNAL_SEGMENTS_CHANGED,
)
from .coordinator import GoveeLocalApiCoordinator, GoveeLocalConfigEntry
from .gradient import RGB, interpolate, parse_colors, scale

_LOGGER = logging.getLogger(__name__)

_NONE_SCENE = "none"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GoveeLocalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Govee light setup."""

    coordinator = config_entry.runtime_data

    def entities_for(device: GoveeDevice) -> list[LightEntity]:
        entities: list[LightEntity] = [GoveeLight(coordinator, device)]
        capabilities = device.capabilities
        if capabilities and GoveeLightFeatures.SEGMENT_CONTROL & capabilities.features:
            entities.extend(
                GoveeSegmentLight(coordinator, device, index)
                for index in range(1, capabilities.segments_count + 1)
            )
        return entities

    def discovery_callback(device: GoveeDevice, is_new: bool) -> bool:
        if is_new:
            async_add_entities(entities_for(device))
        return True

    async_add_entities(
        entity for device in coordinator.devices for entity in entities_for(device)
    )

    await coordinator.set_discovery_callback(discovery_callback)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_GRADIENT,
        {
            vol.Required(ATTR_COLORS): parse_colors,
            vol.Optional(ATTR_BRIGHTNESS_PCT): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
            vol.Optional(ATTR_REVERSE, default=False): cv.boolean,
        },
        "async_set_gradient",
    )


def _device_info(device: GoveeDevice) -> DeviceInfo:
    return DeviceInfo(
        identifiers={
            # Serial numbers are unique identifiers within a specific domain
            (DOMAIN, device.fingerprint)
        },
        name=device.sku,
        manufacturer=MANUFACTURER,
        model_id=device.sku,
        serial_number=device.fingerprint,
    )


class GoveeLight(CoordinatorEntity[GoveeLocalApiCoordinator], LightEntity):
    """Govee Light."""

    _attr_translation_key = "govee_light"
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes: set[ColorMode]
    _fixed_color_mode: ColorMode | None = None
    _attr_effect_list: list[str] | None = None
    _attr_effect: str | None = None
    _attr_supported_features: LightEntityFeature = LightEntityFeature(0)
    _last_color_state: (
        tuple[
            ColorMode | str | None,
            int | None,
            tuple[int, int, int] | tuple[int | None] | None,
        ]
        | None
    ) = None

    def __init__(
        self,
        coordinator: GoveeLocalApiCoordinator,
        device: GoveeDevice,
    ) -> None:
        """Govee Light constructor."""

        super().__init__(coordinator)
        self._device = device

        self._attr_unique_id = device.fingerprint

        capabilities = device.capabilities
        color_modes = {ColorMode.ONOFF}
        if capabilities:
            if GoveeLightFeatures.COLOR_RGB & capabilities.features:
                color_modes.add(ColorMode.RGB)
            if GoveeLightFeatures.COLOR_KELVIN_TEMPERATURE & capabilities.features:
                color_modes.add(ColorMode.COLOR_TEMP)
                self._attr_max_color_temp_kelvin = 9000
                self._attr_min_color_temp_kelvin = 2000
            if GoveeLightFeatures.BRIGHTNESS & capabilities.features:
                color_modes.add(ColorMode.BRIGHTNESS)

            if (
                GoveeLightFeatures.SCENES & capabilities.features
                and capabilities.scenes
            ):
                self._attr_supported_features = LightEntityFeature.EFFECT
                self._attr_effect_list = [_NONE_SCENE, *capabilities.scenes.keys()]

        self._attr_supported_color_modes = filter_supported_color_modes(color_modes)
        if len(self._attr_supported_color_modes) == 1:
            # If the light supports only a single color mode, set it now
            self._fixed_color_mode = next(iter(self._attr_supported_color_modes))

        self._attr_device_info = _device_info(device)

    @property
    @override
    def available(self) -> bool:
        """Return if the device is reachable.

        The underlying library updates ``lastseen`` whenever the device
        replies to a status request. The coordinator polls every
        ``SCAN_INTERVAL``, so if we have not heard back within
        ``DEVICE_TIMEOUT`` we consider the device offline.
        """
        if not super().available:
            return False
        return dt_util.utcnow() - self._device.lastseen < DEVICE_TIMEOUT

    @property
    @override
    def is_on(self) -> bool:
        """Return true if device is on (brightness above 0)."""
        return self._device.on

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self._device.brightness / 100.0) * 255.0)

    @property
    @override
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._device.temperature_color

    @property
    @override
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color."""
        return self._device.rgb_color

    @property
    @override
    def color_mode(self) -> ColorMode:
        """Return the color mode."""
        if self._fixed_color_mode:
            # The light supports only a single color mode, return it
            return self._fixed_color_mode

        # The light supports both color temperature and RGB, determine which
        # mode the light is in
        if (
            self._device.temperature_color is not None
            and self._device.temperature_color > 0
        ):
            return ColorMode.COLOR_TEMP
        return ColorMode.RGB

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness: int = int((float(kwargs[ATTR_BRIGHTNESS]) / 255.0) * 100.0)
            await self.coordinator.set_brightness(self._device, brightness)

        if ATTR_RGB_COLOR in kwargs:
            self._attr_color_mode = ColorMode.RGB
            self._attr_effect = None
            self._last_color_state = None
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            await self.coordinator.set_rgb_color(self._device, red, green, blue)
            self._notify_segments([(red, green, blue)] * self._segments_count)
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_effect = None
            self._last_color_state = None
            temperature: float = kwargs[ATTR_COLOR_TEMP_KELVIN]
            await self.coordinator.set_temperature(self._device, int(temperature))
            self._notify_segments(None)
        elif ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            if effect and self._attr_effect_list and effect in self._attr_effect_list:
                if effect == _NONE_SCENE:
                    self._attr_effect = None
                    await self._restore_last_color_state()
                else:
                    self._attr_effect = effect
                    self._save_last_color_state()
                    await self.coordinator.set_scene(self._device, effect)
                    self._notify_segments(None)

        if not self.is_on or not kwargs:
            await self.coordinator.turn_on(self._device)

        self._write_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.coordinator.turn_off(self._device)
        self._write_state()

    @callback
    def _write_state(self) -> None:
        """Write the state and let the segment entities follow (on/off)."""
        self.async_write_ha_state()
        if self._segments_count:
            async_dispatcher_send(
                self.hass,
                SIGNAL_DEVICE_UPDATED.format(self._device.fingerprint),
            )

    @property
    def _segments_count(self) -> int:
        capabilities = self._device.capabilities
        if capabilities and GoveeLightFeatures.SEGMENT_CONTROL & capabilities.features:
            return capabilities.segments_count
        return 0

    def _notify_segments(self, colors: list[RGB] | None) -> None:
        """Tell the segment entities which colors they show now.

        ``None`` means the colors are unknown (color temperature or scene).
        """
        if self._segments_count:
            async_dispatcher_send(
                self.hass,
                SIGNAL_SEGMENTS_CHANGED.format(self._device.fingerprint),
                colors,
            )

    async def async_set_gradient(
        self,
        colors: list[RGB],
        brightness_pct: int | None = None,
        reverse: bool = False,
    ) -> None:
        """Spread a color gradient over all segments (first color = segment 1)."""
        count = self._segments_count
        if not count:
            raise ServiceValidationError(
                f"{self._device.sku} does not support segment control"
            )
        segment_colors = interpolate(colors, count)
        if reverse:
            segment_colors.reverse()

        if not self.is_on:
            await self.coordinator.turn_on(self._device)
        for index, rgb in enumerate(segment_colors, start=1):
            if index > 1:
                await asyncio.sleep(SEGMENT_SEND_DELAY)
            await self._device.set_segment_rgb_color(index, *rgb)
        if brightness_pct is not None:
            await self.coordinator.set_brightness(self._device, brightness_pct)

        self._attr_effect = None
        self._last_color_state = None
        self._notify_segments(segment_colors)
        self._write_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Register update callback when entity is added."""
        await super().async_added_to_hass()
        self._device.set_update_callback(self._update_callback)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister update callback when entity is removed."""
        self._device.set_update_callback(None)
        await super().async_will_remove_from_hass()

    @callback
    def _update_callback(self, device: GoveeDevice) -> None:
        """Handle device state updates pushed by the library."""
        self._write_state()

    def _save_last_color_state(self) -> None:
        color_mode = self.color_mode
        self._last_color_state = (
            color_mode,
            self.brightness,
            (self.color_temp_kelvin,)
            if color_mode == ColorMode.COLOR_TEMP
            else self.rgb_color,
        )

    async def _restore_last_color_state(self) -> None:
        if self._last_color_state:
            color_mode, brightness, color = self._last_color_state
            if color:
                if color_mode == ColorMode.RGB:
                    await self.coordinator.set_rgb_color(self._device, *color)
                elif color_mode == ColorMode.COLOR_TEMP:
                    await self.coordinator.set_temperature(self._device, *color)
            if brightness:
                await self.coordinator.set_brightness(
                    self._device, int((float(brightness) / 255.0) * 100.0)
                )
            self._last_color_state = None


class GoveeSegmentLight(
    CoordinatorEntity[GoveeLocalApiCoordinator], LightEntity, RestoreEntity
):
    """A single segment of a Govee RGBIC light.

    The device does not report segment colors, so the state is optimistic:
    it is what Home Assistant last sent, and it is restored after a restart.
    Brightness is emulated by scaling the RGB value.
    """

    _attr_translation_key = "segment"
    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_assumed_state = True

    def __init__(
        self,
        coordinator: GoveeLocalApiCoordinator,
        device: GoveeDevice,
        index: int,
    ) -> None:
        """Initialize the segment."""
        super().__init__(coordinator)
        self._device = device
        self._index = index
        self._attr_unique_id = f"{device.fingerprint}_segment_{index}"
        self._attr_translation_placeholders = {"segment": str(index)}
        self._attr_device_info = _device_info(device)
        self._base_rgb: RGB | None = None
        self._seg_brightness: int = 255
        self._seg_on: bool = True

    @property
    @override
    def available(self) -> bool:
        """Segments are available when the lamp is."""
        if not super().available:
            return False
        return dt_util.utcnow() - self._device.lastseen < DEVICE_TIMEOUT

    @property
    @override
    def is_on(self) -> bool:
        """A segment is on when the lamp is on and the segment is not black."""
        return bool(self._device.on and self._seg_on)

    @property
    @override
    def brightness(self) -> int | None:
        """Return the emulated brightness."""
        return self._seg_brightness

    @property
    @override
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the last color sent to this segment (None if unknown)."""
        return self._base_rgb

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the segment color and/or brightness."""
        if ATTR_RGB_COLOR in kwargs:
            self._base_rgb = tuple(kwargs[ATTR_RGB_COLOR])  # type: ignore[assignment]
        if ATTR_BRIGHTNESS in kwargs:
            self._seg_brightness = int(kwargs[ATTR_BRIGHTNESS])
        if self._base_rgb is None:
            self._base_rgb = (255, 255, 255)

        if not self._device.on:
            await self.coordinator.turn_on(self._device)
        await self._device.set_segment_rgb_color(
            self._index, *scale(self._base_rgb, self._seg_brightness)
        )
        self._seg_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the segment dark (the lamp itself stays on)."""
        await self._device.set_segment_rgb_color(self._index, 0, 0, 0)
        self._seg_on = False
        self.async_write_ha_state()

    async def async_set_gradient(self, **kwargs: Any) -> None:
        """Gradients are set on the main light; ignore segments.

        Segments are also hit when the action targets a device or an area,
        so this must not fail.
        """
        _LOGGER.debug(
            "%s: set_gradient ignored on segment, target the main light",
            self.entity_id,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last known segment state and listen for changes."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._seg_on = last.state == STATE_ON
            if (rgb := last.attributes.get(ATTR_RGB_COLOR)) is not None:
                self._base_rgb = tuple(rgb)  # type: ignore[assignment]
            if (brightness := last.attributes.get(ATTR_BRIGHTNESS)) is not None:
                self._seg_brightness = int(brightness)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_SEGMENTS_CHANGED.format(self._device.fingerprint),
                self._segments_changed,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_DEVICE_UPDATED.format(self._device.fingerprint),
                self.async_write_ha_state,
            )
        )

    @callback
    def _segments_changed(self, colors: list[RGB] | None) -> None:
        """Update after the main light changed the whole lamp."""
        if colors is None:
            self._base_rgb = None
        else:
            self._base_rgb = colors[self._index - 1]
        self._seg_brightness = 255
        self._seg_on = True
        self.async_write_ha_state()
