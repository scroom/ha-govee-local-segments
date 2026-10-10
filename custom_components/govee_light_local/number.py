"""Music sensitivity for Govee lights with verified music modes."""

from govee_local_api import GoveeDevice

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import SIGNAL_MUSIC_SENSITIVITY
from .coordinator import GoveeLocalApiCoordinator, GoveeLocalConfigEntry
from .light import _device_info
from .music import DEFAULT_SENSITIVITY, supports_music


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GoveeLocalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up music sensitivity numbers."""
    coordinator = config_entry.runtime_data

    def entities_for(device: GoveeDevice) -> list[GoveeMusicSensitivity]:
        if supports_music(device.sku):
            return [GoveeMusicSensitivity(coordinator, device)]
        return []

    async_add_entities(e for d in coordinator.devices for e in entities_for(d))


class GoveeMusicSensitivity(CoordinatorEntity[GoveeLocalApiCoordinator], RestoreNumber):
    """Microphone sensitivity used by the music effects (0–100 %)."""

    _attr_has_entity_name = True
    _attr_translation_key = "music_sensitivity"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: GoveeLocalApiCoordinator, device: GoveeDevice
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.fingerprint}_music_sensitivity"
        self._attr_device_info = _device_info(device)
        self._attr_native_value = 100.0
        coordinator.music_sensitivity[device.fingerprint] = DEFAULT_SENSITIVITY

    async def async_added_to_hass(self) -> None:
        """Restore the last value."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) is not None:
            if last.native_value is not None:
                self._store(float(last.native_value), notify=False)

    def _store(self, value: float, notify: bool) -> None:
        self._attr_native_value = value
        raw = round(value * 99 / 100)
        self.coordinator.music_sensitivity[self._device.fingerprint] = raw
        if notify:
            async_dispatcher_send(
                self.hass, SIGNAL_MUSIC_SENSITIVITY.format(self._device.fingerprint)
            )

    async def async_set_native_value(self, value: float) -> None:
        """Set the sensitivity; an active music effect is re-sent."""
        self._store(value, notify=True)
        self.async_write_ha_state()
