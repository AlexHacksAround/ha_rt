"""The Service Management integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import area_registry as ar, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .asset_sync import mark_asset_deleted, sync_all_devices, sync_device
from .const import CONF_ADDRESS, CONF_CATALOG, CONF_HA_URL, CONF_QUEUE, CONF_SYNC_INTERVAL, CONF_TOKEN, CONF_URL, DEFAULT_CATALOG, DEFAULT_SYNC_INTERVAL, DOMAIN
from .rt_client import RTClient

_LOGGER = logging.getLogger(__name__)

SERVICE_CREATE_TICKET = "create_ticket"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("subject"): cv.string,
        vol.Required("text"): cv.string,
    }
)

SYNC_SCHEMA = vol.Schema({
    vol.Optional("device_id"): cv.string,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Service Management from a config entry."""
    session = async_get_clientsession(hass)
    client = RTClient(
        session=session,
        url=entry.data[CONF_URL],
        token=entry.data[CONF_TOKEN],
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "url": entry.data[CONF_URL],
        "queue": entry.data[CONF_QUEUE],
        "ha_url": entry.data.get(CONF_HA_URL, ""),
        "address": entry.data.get(CONF_ADDRESS, ""),
        "catalog": entry.data.get(CONF_CATALOG, DEFAULT_CATALOG),
        "sync_interval": entry.data.get(CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL),
    }

    async def handle_create_ticket(call: ServiceCall) -> ServiceResponse:
        """Handle create_ticket service call with deduplication."""
        device_id = call.data["device_id"]
        subject = call.data["subject"]
        text = call.data["text"]

        # Get first configured entry's data
        entry_data = next(iter(hass.data[DOMAIN].values()))
        rt_client: RTClient = entry_data["client"]
        queue: str = entry_data["queue"]
        base_url: str = entry_data["url"]
        configured_ha_url: str = entry_data["ha_url"]
        address: str = entry_data["address"]
        catalog: str = entry_data["catalog"]

        # Look up device info (only what's needed for tickets)
        area_name = ""
        device_name = device_id  # Fallback to device_id if name not available
        if device_id:
            device_registry = dr.async_get(hass)
            device = device_registry.async_get(device_id)
            if device:
                # Use user-customized name, or default name, or device_id as fallback
                device_name = device.name_by_user or device.name or device_id
                if device.area_id:
                    area_registry = ar.async_get(hass)
                    area = area_registry.async_get_area(device.area_id)
                    if area:
                        area_name = area.name

        # Build device info URL
        device_info_url = ""
        if device_id:
            # Use configured URL if set, otherwise try to auto-detect
            if configured_ha_url:
                ha_url = configured_ha_url.rstrip("/")
                device_info_url = f"{ha_url}/config/devices/device/{device_id}"
            else:
                try:
                    ha_url = get_url(hass)
                    device_info_url = f"{ha_url}/config/devices/device/{device_id}"
                except NoURLAvailableError:
                    _LOGGER.warning("No HA URL configured, skipping Device Information")

        # Get asset for this device (should already exist from sync)
        asset_id = None
        if device_id:
            existing_asset = await rt_client.search_asset(catalog, device_id)
            if existing_asset:
                asset_id = existing_asset.get("id")
                _LOGGER.debug("Found asset %s for device %s", asset_id, device_id)
            else:
                _LOGGER.warning(
                    "Asset not found for device %s. Run sync_assets service.",
                    device_id
                )

        # Search for existing open ticket linked to this asset with same subject
        existing = []
        if asset_id:
            existing = await rt_client.search_tickets_for_asset(queue, asset_id, subject)

        if existing:
            # Add comment to first open ticket
            ticket_id = existing[0]["id"]
            await rt_client.add_comment(ticket_id, text)
            action = "commented"
        else:
            # Create new ticket
            result = await rt_client.create_ticket(
                queue, subject, text, device_id, device_info_url,
                area=area_name, address=address
            )
            ticket_id = result["id"]
            action = "created"
            # Link ticket to asset
            if asset_id:
                linked = await rt_client.link_ticket_to_asset(ticket_id, asset_id)
                if linked:
                    _LOGGER.debug("Linked ticket %s to asset %s", ticket_id, asset_id)

        ticket_url = f"{base_url.rstrip('/')}/Ticket/Display.html?id={ticket_id}"

        return {
            "ticket_id": ticket_id,
            "ticket_url": ticket_url,
            "action": action,
        }

    async def handle_sync_assets(call: ServiceCall) -> ServiceResponse:
        """Handle sync_assets service call."""
        device_id = call.data.get("device_id")

        entry_data = next(iter(hass.data[DOMAIN].values()))
        rt_client: RTClient = entry_data["client"]
        catalog: str = entry_data["catalog"]

        if device_id:
            success = await sync_device(hass, rt_client, catalog, device_id)
            return {"synced": 1 if success else 0, "failed": 0 if success else 1}
        else:
            return await sync_all_devices(hass, rt_client, catalog)

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_TICKET,
        handle_create_ticket,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "sync_assets",
        handle_sync_assets,
        schema=SYNC_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    async def handle_device_registry_event(event):
        """Handle device registry changes."""
        action = event.data.get("action")
        device_id = event.data.get("device_id")

        if not device_id:
            return

        entry_data = next(iter(hass.data[DOMAIN].values()), None)
        if not entry_data:
            return

        rt_client: RTClient = entry_data["client"]
        catalog: str = entry_data["catalog"]

        try:
            if action in ("create", "update"):
                await sync_device(hass, rt_client, catalog, device_id)
                _LOGGER.debug("Synced device %s after %s event", device_id, action)
            elif action == "remove":
                await mark_asset_deleted(rt_client, catalog, device_id)
        except Exception as err:
            _LOGGER.error("Failed to handle device %s %s: %s", device_id, action, err)

    entry.async_on_unload(
        hass.bus.async_listen("device_registry_updated", handle_device_registry_event)
    )

    sync_interval = entry.data.get(CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL)

    async def scheduled_sync(now):
        """Run periodic full asset sync."""
        entry_data = next(iter(hass.data[DOMAIN].values()), None)
        if not entry_data:
            return

        rt_client: RTClient = entry_data["client"]
        catalog: str = entry_data["catalog"]

        _LOGGER.debug("Starting scheduled asset sync")
        await sync_all_devices(hass, rt_client, catalog)

    entry.async_on_unload(
        async_track_time_interval(hass, scheduled_sync, timedelta(hours=sync_interval))
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_CREATE_TICKET)
        hass.services.async_remove(DOMAIN, "sync_assets")

    return True
