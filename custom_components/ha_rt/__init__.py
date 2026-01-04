"""The Service Management integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_QUEUE, CONF_TOKEN, CONF_URL, DOMAIN
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

        # Search for existing open ticket
        existing = await rt_client.search_tickets(queue, device_id)

        if existing:
            # Add comment to first open ticket
            ticket_id = existing[0]["id"]
            await rt_client.add_comment(ticket_id, text)
            action = "commented"
        else:
            # Create new ticket
            result = await rt_client.create_ticket(queue, subject, text, device_id)
            ticket_id = result["id"]
            action = "created"

        ticket_url = f"{base_url.rstrip('/')}/Ticket/Display.html?id={ticket_id}"

        return {
            "ticket_id": ticket_id,
            "ticket_url": ticket_url,
            "action": action,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_TICKET,
        handle_create_ticket,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_CREATE_TICKET)

    return True
