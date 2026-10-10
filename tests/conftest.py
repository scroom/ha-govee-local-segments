"""Fixtures for the segment fork of govee_light_local."""

from asyncio import Event
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from govee_local_api import GoveeController, GoveeDevice, GoveeLightCapabilities
from govee_local_api.light_capabilities import GOVEE_LIGHT_CAPABILITIES
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

import custom_components.govee_light_local.coordinator  # noqa: F401,E402

DOMAIN = "govee_light_local"
H6076 = GOVEE_LIGHT_CAPABILITIES["H6076"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the integration from custom_components."""
    return


@pytest.fixture(name="mock_govee_api")
def fixture_mock_govee_api() -> Generator[AsyncMock]:
    """Mock the library controller (no network traffic)."""
    mock_api = AsyncMock(spec=GoveeController)
    mock_api.cleanup = MagicMock(return_value=Event())
    mock_api.cleanup.return_value.set()
    with patch(
        "custom_components.govee_light_local.coordinator.GoveeController",
        return_value=mock_api,
    ):
        yield mock_api


async def setup_light(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    capabilities: GoveeLightCapabilities = H6076,
    sku: str = "H6076",
) -> tuple[MockConfigEntry, GoveeDevice]:
    """Set up one mocked device."""
    device = GoveeDevice(
        controller=mock_govee_api,
        ip="192.168.188.117",
        fingerprint="AA:BB:CC:DD",
        sku=sku,
        capabilities=capabilities,
    )
    device._is_on = True  # noqa: SLF001
    mock_govee_api.devices = [device]
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, device
