"""Asset synchronization between Home Assistant and RT."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .rt_client import RTClient

_LOGGER = logging.getLogger(__name__)


async def sync_device(
    hass: HomeAssistant,
    rt_client: RTClient,
    catalog: str,
    device_id: str,
) -> bool:
    """Sync a single device to RT. Returns True on success."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if not device:
        _LOGGER.warning("Device not found: %s", device_id)
        return False

    # Extract device info
    device_name = device.name_by_user or device.name or device_id
    manufacturer = device.manufacturer or ""
    model = device.model or ""
    serial_number = device.serial_number or ""
    sw_version = device.sw_version or ""
    hw_version = device.hw_version or ""
    config_url = str(device.configuration_url) if device.configuration_url else ""

    # Extract MAC address
    mac_address = ""
    for conn_type, conn_id in device.connections:
        if conn_type == "mac":
            mac_address = conn_id
            break

    # Search for existing asset
    existing_asset = await rt_client.search_asset(catalog, device_id)

    if existing_asset:
        # Update existing asset
        asset_id = existing_asset.get("id")
        success = await rt_client.update_asset(
            asset_id,
            name=device_name,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            sw_version=sw_version,
            hw_version=hw_version,
            config_url=config_url,
            mac_address=mac_address,
        )
        if success:
            _LOGGER.debug("Updated asset %s for device %s", asset_id, device_id)
        return success
    else:
        # Create new asset
        new_asset = await rt_client.create_asset(
            catalog,
            device_name,
            device_id,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            sw_version=sw_version,
            hw_version=hw_version,
            config_url=config_url,
            mac_address=mac_address,
        )
        if new_asset:
            _LOGGER.debug("Created asset %s for device %s", new_asset.get("id"), device_id)
            return True
        return False
