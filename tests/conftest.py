"""Pytest fixtures for ha_rt tests."""

from unittest.mock import AsyncMock, MagicMock
import pytest


@pytest.fixture
def mock_rt_client():
    """Create a mock RT client."""
    client = AsyncMock()
    client.test_connection = AsyncMock(return_value=True)
    client.search_tickets = AsyncMock(return_value=[])
    client.search_asset = AsyncMock(return_value=None)
    client.create_asset = AsyncMock(return_value={"id": 123})
    client.update_asset = AsyncMock(return_value=True)
    client.search_tickets_for_asset = AsyncMock(return_value=[])
    client.create_ticket = AsyncMock(return_value={"id": 456})
    client.add_comment = AsyncMock(return_value=None)
    client.link_ticket_to_asset = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_device():
    """Create a mock device registry entry."""
    device = MagicMock()
    device.id = "test-device-id-123"
    device.name = "Test Device"
    device.name_by_user = None
    device.manufacturer = "Test Manufacturer"
    device.model = "Test Model"
    device.serial_number = "SN123"
    device.sw_version = "1.0.0"
    device.hw_version = "2.0"
    device.configuration_url = "http://192.168.1.100"
    device.connections = {("mac", "aa:bb:cc:dd:ee:ff")}
    device.area_id = None
    return device


@pytest.fixture
def mock_device_registry(mock_device):
    """Create a mock device registry."""
    registry = MagicMock()
    registry.devices = MagicMock()
    registry.devices.values.return_value = [mock_device]
    registry.async_get.return_value = mock_device
    return registry


@pytest.fixture
def mock_hass(mock_device_registry):
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    return hass
