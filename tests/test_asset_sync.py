"""Tests for asset sync module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_sync_device_creates_new_asset():
    """Test sync_device creates asset when none exists."""
    from custom_components.ha_rt.asset_sync import sync_device

    mock_rt_client = AsyncMock()
    mock_rt_client.search_asset = AsyncMock(return_value=None)
    mock_rt_client.create_asset = AsyncMock(return_value={"id": 123})

    mock_device = MagicMock()
    mock_device.id = "device-123"
    mock_device.name = "Test Device"
    mock_device.name_by_user = None
    mock_device.manufacturer = "Acme"
    mock_device.model = "Widget"
    mock_device.serial_number = "SN001"
    mock_device.sw_version = "1.0"
    mock_device.hw_version = "2.0"
    mock_device.configuration_url = None
    mock_device.connections = set()

    mock_registry = MagicMock()
    mock_registry.async_get.return_value = mock_device

    mock_hass = MagicMock()

    with patch(
        "custom_components.ha_rt.asset_sync.dr.async_get",
        return_value=mock_registry
    ):
        result = await sync_device(mock_hass, mock_rt_client, "TestCatalog", "device-123")

    assert result is True
    mock_rt_client.create_asset.assert_called_once()
    call_kwargs = mock_rt_client.create_asset.call_args
    assert call_kwargs[0][0] == "TestCatalog"
    assert call_kwargs[0][1] == "Test Device"


@pytest.mark.asyncio
async def test_sync_device_updates_existing_asset():
    """Test sync_device updates asset when it exists."""
    from custom_components.ha_rt.asset_sync import sync_device

    mock_rt_client = AsyncMock()
    mock_rt_client.search_asset = AsyncMock(return_value={"id": 456})
    mock_rt_client.update_asset = AsyncMock(return_value=True)

    mock_device = MagicMock()
    mock_device.id = "device-123"
    mock_device.name = "Updated Device"
    mock_device.name_by_user = "My Custom Name"
    mock_device.manufacturer = "Acme"
    mock_device.model = "Widget Pro"
    mock_device.serial_number = None
    mock_device.sw_version = "2.0"
    mock_device.hw_version = None
    mock_device.configuration_url = None
    mock_device.connections = set()

    mock_registry = MagicMock()
    mock_registry.async_get.return_value = mock_device

    mock_hass = MagicMock()

    with patch(
        "custom_components.ha_rt.asset_sync.dr.async_get",
        return_value=mock_registry
    ):
        result = await sync_device(mock_hass, mock_rt_client, "TestCatalog", "device-123")

    assert result is True
    mock_rt_client.update_asset.assert_called_once()
    call_kwargs = mock_rt_client.update_asset.call_args
    assert call_kwargs[0][0] == 456  # asset_id
    assert call_kwargs[1]["name"] == "My Custom Name"  # Uses name_by_user


@pytest.mark.asyncio
async def test_sync_all_devices():
    """Test sync_all_devices syncs all devices."""
    from custom_components.ha_rt.asset_sync import sync_all_devices

    mock_rt_client = AsyncMock()
    mock_rt_client.search_asset = AsyncMock(return_value=None)
    mock_rt_client.create_asset = AsyncMock(return_value={"id": 123})

    mock_device1 = MagicMock()
    mock_device1.id = "device-1"
    mock_device1.name = "Device 1"
    mock_device1.name_by_user = None
    mock_device1.manufacturer = ""
    mock_device1.model = ""
    mock_device1.serial_number = None
    mock_device1.sw_version = None
    mock_device1.hw_version = None
    mock_device1.configuration_url = None
    mock_device1.connections = set()

    mock_device2 = MagicMock()
    mock_device2.id = "device-2"
    mock_device2.name = "Device 2"
    mock_device2.name_by_user = None
    mock_device2.manufacturer = ""
    mock_device2.model = ""
    mock_device2.serial_number = None
    mock_device2.sw_version = None
    mock_device2.hw_version = None
    mock_device2.configuration_url = None
    mock_device2.connections = set()

    mock_registry = MagicMock()
    mock_registry.devices.values.return_value = [mock_device1, mock_device2]
    mock_registry.async_get.side_effect = lambda did: mock_device1 if did == "device-1" else mock_device2

    mock_hass = MagicMock()

    with patch(
        "custom_components.ha_rt.asset_sync.dr.async_get",
        return_value=mock_registry
    ):
        result = await sync_all_devices(mock_hass, mock_rt_client, "TestCatalog")

    assert result["synced"] == 2
    assert result["failed"] == 0
    assert mock_rt_client.create_asset.call_count == 2


@pytest.mark.asyncio
async def test_sync_all_continues_after_failure():
    """Test sync_all_devices continues when one device fails."""
    from custom_components.ha_rt.asset_sync import sync_all_devices

    mock_rt_client = AsyncMock()
    # First call fails, second succeeds
    mock_rt_client.search_asset = AsyncMock(return_value=None)
    mock_rt_client.create_asset = AsyncMock(side_effect=[None, {"id": 123}])

    mock_device1 = MagicMock()
    mock_device1.id = "device-1"
    mock_device1.name = "Device 1"
    mock_device1.name_by_user = None
    mock_device1.manufacturer = ""
    mock_device1.model = ""
    mock_device1.serial_number = None
    mock_device1.sw_version = None
    mock_device1.hw_version = None
    mock_device1.configuration_url = None
    mock_device1.connections = set()

    mock_device2 = MagicMock()
    mock_device2.id = "device-2"
    mock_device2.name = "Device 2"
    mock_device2.name_by_user = None
    mock_device2.manufacturer = ""
    mock_device2.model = ""
    mock_device2.serial_number = None
    mock_device2.sw_version = None
    mock_device2.hw_version = None
    mock_device2.configuration_url = None
    mock_device2.connections = set()

    mock_registry = MagicMock()
    mock_registry.devices.values.return_value = [mock_device1, mock_device2]
    mock_registry.async_get.side_effect = lambda did: mock_device1 if did == "device-1" else mock_device2

    mock_hass = MagicMock()

    with patch(
        "custom_components.ha_rt.asset_sync.dr.async_get",
        return_value=mock_registry
    ):
        result = await sync_all_devices(mock_hass, mock_rt_client, "TestCatalog")

    assert result["synced"] == 1
    assert result["failed"] == 1
    assert mock_rt_client.create_asset.call_count == 2  # Both were attempted