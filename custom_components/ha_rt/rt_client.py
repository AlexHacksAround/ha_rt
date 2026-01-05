"""RT REST2 API client."""

from __future__ import annotations

import logging
import re
from typing import Any

from aiohttp import ClientSession, ClientError

from .const import ADDRESS_FIELD, AREA_FIELD, DEVICE_ID_FIELD, DEVICE_INFO_FIELD, OPEN_STATUSES
from .exceptions import CannotConnect, InvalidAuth, RTAPIError

_LOGGER = logging.getLogger(__name__)


def _escape_ticketsql(value: str) -> str:
    r"""Escape special characters for TicketSQL queries.

    TicketSQL uses double quotes for string values. We need to:
    1. Escape backslashes first (\ -> \\)
    2. Escape double quotes (" -> \")
    """
    if not isinstance(value, str):
        value = str(value)
    # Escape backslashes first, then quotes
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    return value


class RTClient:
    """Client for RT REST2 API."""

    def __init__(self, session: ClientSession, url: str, token: str) -> None:
        """Initialize the RT client."""
        self.session = session
        self.base_url = url.rstrip("/")
        self.token = token

    def _headers(self) -> dict[str, str]:
        """Return headers for RT API requests."""
        return {
            "Authorization": f"token {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def test_connection(self) -> bool:
        """Test the connection to RT. Returns True if successful."""
        try:
            async with self.session.get(
                f"{self.base_url}/REST/2.0/rt",
                headers=self._headers(),
            ) as response:
                if response.status == 401:
                    raise InvalidAuth("Invalid API token")
                if response.status == 403:
                    raise InvalidAuth("API token lacks permissions")
                if response.status != 200:
                    raise RTAPIError(f"RT API error: {response.status}")
                return True
        except ClientError as err:
            raise CannotConnect(f"Cannot connect to RT: {err}") from err

    async def search_tickets(
        self, queue: str, device_id: str
    ) -> list[dict[str, Any]]:
        """Search for open tickets with matching device_id."""
        # Escape user input to prevent TicketSQL injection
        safe_queue = _escape_ticketsql(queue)
        safe_device_id = _escape_ticketsql(device_id)

        statuses = " OR ".join(f'Status="{s}"' for s in OPEN_STATUSES)
        query = (
            f'Queue="{safe_queue}" AND ({statuses}) '
            f'AND CF.{{{DEVICE_ID_FIELD}}}="{safe_device_id}"'
        )

        try:
            async with self.session.get(
                f"{self.base_url}/REST/2.0/tickets",
                headers=self._headers(),
                params={"query": query},
            ) as response:
                if response.status != 200:
                    raise RTAPIError(f"Search failed: {response.status}")
                data = await response.json()
                return data.get("items", [])
        except ClientError as err:
            raise CannotConnect(f"Cannot connect to RT: {err}") from err

    async def search_asset(self, catalog: str, device_id: str) -> dict[str, Any] | None:
        """Search for an asset by device_id. Returns asset dict or None."""
        safe_catalog = _escape_ticketsql(catalog)
        safe_device_id = _escape_ticketsql(device_id)

        query = f'Catalog="{safe_catalog}" AND CF.{{{DEVICE_ID_FIELD}}}="{safe_device_id}"'

        try:
            async with self.session.get(
                f"{self.base_url}/REST/2.0/assets",
                headers=self._headers(),
                params={"query": query},
            ) as response:
                if response.status != 200:
                    _LOGGER.warning("Asset search failed: %s", response.status)
                    return None
                data = await response.json()
                items = data.get("items", [])
                return items[0] if items else None
        except ClientError as err:
            _LOGGER.warning("Asset search error: %s", err)
            return None

    async def create_asset(
        self, catalog: str, name: str, device_id: str, device_info_url: str = ""
    ) -> dict[str, Any] | None:
        """Create a new asset. Returns dict with 'id' or None on failure."""
        custom_fields: dict[str, str] = {DEVICE_ID_FIELD: device_id}
        if device_info_url:
            custom_fields[DEVICE_INFO_FIELD] = device_info_url

        payload = {
            "Name": name,
            "Catalog": catalog,
            "CustomFields": custom_fields,
        }

        try:
            async with self.session.post(
                f"{self.base_url}/REST/2.0/asset",
                headers=self._headers(),
                json=payload,
            ) as response:
                if response.status not in (200, 201):
                    resp_text = await response.text()
                    _LOGGER.warning("Asset create failed: %s - %s", response.status, resp_text)
                    return None
                data = await response.json()
                return {"id": data.get("id")}
        except ClientError as err:
            _LOGGER.warning("Asset create error: %s", err)
            return None

    async def link_ticket_to_asset(self, ticket_id: int, asset_id: int) -> bool:
        """Link a ticket to an asset using RefersTo. Returns True on success."""
        payload = {"RefersTo": f"asset:{asset_id}"}

        try:
            async with self.session.put(
                f"{self.base_url}/REST/2.0/ticket/{ticket_id}",
                headers=self._headers(),
                json=payload,
            ) as response:
                if response.status not in (200, 201):
                    resp_text = await response.text()
                    _LOGGER.warning("Link failed: %s - %s", response.status, resp_text)
                    return False
                return True
        except ClientError as err:
            _LOGGER.warning("Link error: %s", err)
            return False

    async def create_ticket(
        self,
        queue: str,
        subject: str,
        text: str,
        device_id: str,
        device_info_url: str = "",
        area: str = "",
        address: str = "",
    ) -> dict[str, Any]:
        """Create a new ticket. Returns dict with 'id'."""
        custom_fields: dict[str, str] = {DEVICE_ID_FIELD: device_id}
        if device_info_url:
            custom_fields[DEVICE_INFO_FIELD] = device_info_url
        if area:
            custom_fields[AREA_FIELD] = area
        if address:
            custom_fields[ADDRESS_FIELD] = address

        # Build ticket content with location info
        content_parts = [text]
        if area or address:
            content_parts.append("")  # blank line
            if address:
                content_parts.append(f"Location: {address}")
            if area:
                content_parts.append(f"Area: {area}")
        content = "\n".join(content_parts)

        payload = {
            "Queue": queue,
            "Subject": subject,
            "Content": content,
            "CustomFields": custom_fields,
        }

        try:
            async with self.session.post(
                f"{self.base_url}/REST/2.0/ticket",
                headers=self._headers(),
                json=payload,
            ) as response:
                if response.status not in (200, 201):
                    resp_text = await response.text()
                    raise RTAPIError(f"Create failed: {response.status} - {resp_text}")
                data = await response.json()
                return {"id": data.get("id")}
        except ClientError as err:
            raise CannotConnect(f"Cannot connect to RT: {err}") from err

    async def add_comment(self, ticket_id: int, text: str) -> None:
        """Add a comment to an existing ticket."""
        headers = {
            "Authorization": f"token {self.token}",
            "Content-Type": "text/plain",
        }

        try:
            async with self.session.post(
                f"{self.base_url}/REST/2.0/ticket/{ticket_id}/comment",
                headers=headers,
                data=text,
            ) as response:
                if response.status not in (200, 201):
                    raise RTAPIError(f"Comment failed: {response.status}")
        except ClientError as err:
            raise CannotConnect(f"Cannot connect to RT: {err}") from err
