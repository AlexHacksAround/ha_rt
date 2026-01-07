"""Asset synchronization between Home Assistant and RT."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import area_registry as ar, device_registry as dr

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .rt_client import RTClient

_LOGGER = logging.getLogger(__name__)


async def sync_device(
    hass: HomeAssistant,
    rt_client: RTClient,
    catalog: str,
    device_id: str,
    address: str = "",
) -> bool | None:
    """Sync a single device to RT.

    Returns:
        True: Success
        False: Failed
        None: Skipped (not a physical device)
    """
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if not device:
        _LOGGER.warning("Device not found: %s", device_id)
        return False

    # Skip non-physical devices (services, integrations, add-ons, etc.)
    if device.entry_type is not None:
        _LOGGER.debug(
            "Skipping non-physical device %s (entry_type=%s)",
            device_id,
            device.entry_type,
        )
        return None

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

    # Look up area name
    area_name = ""
    if device.area_id:
        area_registry = ar.async_get(hass)
        area = area_registry.async_get_area(device.area_id)
        if area:
            area_name = area.name

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
            area=area_name,
            address=address,
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
            area=area_name,
            address=address,
        )
        if new_asset:
            _LOGGER.debug("Created asset %s for device %s", new_asset.get("id"), device_id)
            return True
        return False


async def sync_all_devices(
    hass: HomeAssistant,
    rt_client: RTClient,
    catalog: str,
    cleanup: bool = True,
    address: str = "",
) -> dict[str, int]:
    """Sync all devices to RT. Returns counts of synced/failed/skipped/deleted."""
    results = {"synced": 0, "failed": 0, "skipped": 0, "deleted": 0}
    device_registry = dr.async_get(hass)

    for device in device_registry.devices.values():
        try:
            result = await sync_device(hass, rt_client, catalog, device.id, address=address)
            if result is True:
                results["synced"] += 1
            elif result is False:
                results["failed"] += 1
            else:  # None = skipped
                results["skipped"] += 1
        except Exception as err:
            _LOGGER.error("Failed to sync device %s: %s", device.id, err)
            results["failed"] += 1

    # Clean up orphaned assets (devices that no longer exist in HA)
    if cleanup:
        results["deleted"] = await cleanup_orphaned_assets(hass, rt_client, catalog)

    _LOGGER.info(
        "Asset sync complete: %d synced, %d failed, %d skipped, %d deleted",
        results["synced"],
        results["failed"],
        results["skipped"],
        results["deleted"],
    )
    return results


async def mark_asset_deleted(
    rt_client: RTClient,
    catalog: str,
    device_id: str,
) -> bool:
    """Mark an asset as deleted in RT when device is removed from HA.

    Returns True if asset was found and marked deleted, False otherwise.
    """
    existing_asset = await rt_client.search_asset(catalog, device_id)

    if not existing_asset:
        _LOGGER.debug("No asset found for removed device %s", device_id)
        return False

    asset_id = existing_asset.get("id")
    success = await rt_client.update_asset(asset_id, status="deleted")

    if success:
        _LOGGER.info("Marked asset %s as deleted for device %s", asset_id, device_id)
    else:
        _LOGGER.warning("Failed to mark asset %s as deleted", asset_id)

    return success


async def cleanup_orphaned_assets(
    hass: HomeAssistant,
    rt_client: RTClient,
    catalog: str,
) -> int:
    """Find RT assets that should not exist and mark them deleted.

    An asset should be deleted if:
    - The device no longer exists in HA
    - The device exists but is non-physical (integration, add-on, service, etc.)

    Returns count of assets marked as deleted.
    """
    from .const import DEVICE_ID_FIELD

    device_registry = dr.async_get(hass)

    # Build set of valid physical device IDs (entry_type is None for physical devices)
    valid_device_ids = {
        device.id
        for device in device_registry.devices.values()
        if device.entry_type is None
    }

    # Get all active assets from RT (excludes deleted and stolen)
    assets = await rt_client.list_assets(catalog)
    deleted_count = 0

    for asset_ref in assets:
        asset_id = asset_ref.get("id")
        if not asset_id:
            continue

        # Get full asset details to read DeviceId custom field
        asset = await rt_client.get_asset(asset_id)
        if not asset:
            continue

        # Extract DeviceId from custom fields
        custom_fields = asset.get("CustomFields", {})
        device_id = None
        for cf in custom_fields:
            if cf.get("name") == DEVICE_ID_FIELD:
                device_id = cf.get("values", [""])[0]
                break

        if not device_id:
            continue

        # Check if device is valid (exists and is physical)
        if device_id not in valid_device_ids:
            success = await rt_client.update_asset(asset_id, status="deleted")
            if success:
                _LOGGER.info(
                    "Marked asset %s as deleted (device %s is invalid or non-physical)",
                    asset_id,
                    device_id,
                )
                deleted_count += 1

    return deleted_count
