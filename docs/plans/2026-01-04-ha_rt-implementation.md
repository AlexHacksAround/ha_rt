# ha_rt Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a HACS-compatible Home Assistant integration that creates RT tickets with built-in deduplication.

**Architecture:** Config flow collects URL/Token/Queue, RTClient handles REST2 API, single service `ha_rt.create_ticket` searches for existing tickets before creating/commenting.

**Tech Stack:** Python 3.11+, aiohttp, Home Assistant Core APIs, voluptuous for schema validation

---

## Task 1: Create Directory Structure and Constants

**Files:**
- Create: `custom_components/ha_rt/__init__.py` (empty for now)
- Create: `custom_components/ha_rt/const.py`

**Step 1: Create directory structure**

```bash
mkdir -p custom_components/ha_rt
```

**Step 2: Create const.py with domain and constants**

```python
"""Constants for the Service Management integration."""

DOMAIN = "ha_rt"

# RT API constants
DEVICE_ID_FIELD = "DeviceId"
OPEN_STATUSES = ["new", "open", "stalled"]

# Config keys
CONF_URL = "url"
CONF_TOKEN = "token"
CONF_QUEUE = "queue"

# Defaults
DEFAULT_QUEUE = "Facility Management"
```

**Step 3: Create empty __init__.py placeholder**

```python
"""The Service Management integration."""
```

**Step 4: Verify files exist**

Run: `ls -la custom_components/ha_rt/`
Expected: `__init__.py`, `const.py`

---

## Task 2: Create Custom Exceptions

**Files:**
- Create: `custom_components/ha_rt/exceptions.py`

**Step 1: Create exceptions module**

```python
"""Exceptions for the Service Management integration."""

from homeassistant.exceptions import HomeAssistantError


class RTError(HomeAssistantError):
    """Base exception for RT errors."""


class CannotConnect(RTError):
    """Error to indicate we cannot connect to RT."""


class InvalidAuth(RTError):
    """Error to indicate invalid authentication."""


class RTAPIError(RTError):
    """Error to indicate RT API returned an error."""
```

**Step 2: Verify file exists**

Run: `cat custom_components/ha_rt/exceptions.py`
Expected: Shows exception classes

---

## Task 3: Create RT Client

**Files:**
- Create: `custom_components/ha_rt/rt_client.py`

**Step 1: Create RT client with all methods**

```python
"""RT REST2 API client."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession, ClientError

from .const import DEVICE_ID_FIELD, OPEN_STATUSES
from .exceptions import CannotConnect, InvalidAuth, RTAPIError

_LOGGER = logging.getLogger(__name__)


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
                f"{self.base_url}/REST/2.0/user",
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
        statuses = " OR ".join(f'Status="{s}"' for s in OPEN_STATUSES)
        query = (
            f'Queue="{queue}" AND ({statuses}) '
            f'AND CF.{{{DEVICE_ID_FIELD}}}="{device_id}"'
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

    async def create_ticket(
        self,
        queue: str,
        subject: str,
        text: str,
        device_id: str,
    ) -> dict[str, Any]:
        """Create a new ticket. Returns dict with 'id'."""
        payload = {
            "Queue": queue,
            "Subject": subject,
            "Content": text,
            "CustomFields": {DEVICE_ID_FIELD: device_id},
        }

        try:
            async with self.session.post(
                f"{self.base_url}/REST/2.0/ticket",
                headers=self._headers(),
                json=payload,
            ) as response:
                if response.status not in (200, 201):
                    text = await response.text()
                    raise RTAPIError(f"Create failed: {response.status} - {text}")
                data = await response.json()
                return {"id": data.get("id")}
        except ClientError as err:
            raise CannotConnect(f"Cannot connect to RT: {err}") from err

    async def add_comment(self, ticket_id: int, text: str) -> None:
        """Add a comment to an existing ticket."""
        payload = {
            "Content": text,
        }

        try:
            async with self.session.post(
                f"{self.base_url}/REST/2.0/ticket/{ticket_id}/comment",
                headers=self._headers(),
                json=payload,
            ) as response:
                if response.status not in (200, 201):
                    raise RTAPIError(f"Comment failed: {response.status}")
        except ClientError as err:
            raise CannotConnect(f"Cannot connect to RT: {err}") from err
```

**Step 2: Verify file syntax**

Run: `python3 -m py_compile custom_components/ha_rt/rt_client.py && echo "Syntax OK"`
Expected: `Syntax OK`

---

## Task 4: Create Config Flow

**Files:**
- Create: `custom_components/ha_rt/config_flow.py`

**Step 1: Create config flow with validation**

```python
"""Config flow for Service Management integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_QUEUE, CONF_TOKEN, CONF_URL, DEFAULT_QUEUE, DOMAIN
from .exceptions import CannotConnect, InvalidAuth
from .rt_client import RTClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_QUEUE, default=DEFAULT_QUEUE): str,
    }
)


class HARTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Service Management."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                session = async_get_clientsession(self.hass)
                client = RTClient(
                    session=session,
                    url=user_input[CONF_URL],
                    token=user_input[CONF_TOKEN],
                )
                await client.test_connection()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                title = f"Service Management ({user_input[CONF_QUEUE]})"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
```

**Step 2: Verify file syntax**

Run: `python3 -m py_compile custom_components/ha_rt/config_flow.py && echo "Syntax OK"`
Expected: `Syntax OK`

---

## Task 5: Create Strings for UI

**Files:**
- Create: `custom_components/ha_rt/strings.json`

**Step 1: Create strings.json**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to Request Tracker",
        "description": "Enter your RT server details. See documentation for RT prerequisites.",
        "data": {
          "url": "RT Server URL",
          "token": "API Token",
          "queue": "Queue Name"
        }
      }
    },
    "error": {
      "cannot_connect": "Cannot connect to RT server. Check the URL.",
      "invalid_auth": "Invalid API token or insufficient permissions.",
      "unknown": "Unexpected error occurred."
    },
    "abort": {
      "already_configured": "This RT server is already configured."
    }
  },
  "services": {
    "create_ticket": {
      "name": "Create or update ticket",
      "description": "Creates a new ticket or comments on existing open ticket for the device.",
      "fields": {
        "device_id": {
          "name": "Device ID",
          "description": "Unique identifier for the device/entity."
        },
        "subject": {
          "name": "Subject",
          "description": "Ticket subject line (used for new tickets)."
        },
        "text": {
          "name": "Text",
          "description": "Ticket body or comment text."
        }
      }
    }
  }
}
```

**Step 2: Validate JSON syntax**

Run: `python3 -c "import json; json.load(open('custom_components/ha_rt/strings.json'))" && echo "JSON OK"`
Expected: `JSON OK`

---

## Task 6: Create Services Definition

**Files:**
- Create: `custom_components/ha_rt/services.yaml`

**Step 1: Create services.yaml**

```yaml
create_ticket:
  fields:
    device_id:
      required: true
      example: "sensor.water_leak_kitchen"
      selector:
        text:
    subject:
      required: true
      example: "Water leak detected"
      selector:
        text:
    text:
      required: true
      example: "Sensor triggered at 10:30 AM"
      selector:
        text:
          multiline: true
```

**Step 2: Validate YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('custom_components/ha_rt/services.yaml'))" && echo "YAML OK"`
Expected: `YAML OK`

---

## Task 7: Create Main Integration Entry Point

**Files:**
- Modify: `custom_components/ha_rt/__init__.py`

**Step 1: Implement __init__.py with service registration**

```python
"""The Service Management integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
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
```

**Step 2: Verify file syntax**

Run: `python3 -m py_compile custom_components/ha_rt/__init__.py && echo "Syntax OK"`
Expected: `Syntax OK`

---

## Task 8: Create Manifest

**Files:**
- Create: `custom_components/ha_rt/manifest.json`

**Step 1: Create manifest.json**

```json
{
  "domain": "ha_rt",
  "name": "Service Management",
  "version": "1.0.0",
  "documentation": "https://github.com/USERNAME/ha_rt",
  "issue_tracker": "https://github.com/USERNAME/ha_rt/issues",
  "codeowners": ["@USERNAME"],
  "dependencies": [],
  "requirements": [],
  "config_flow": true,
  "integration_type": "service",
  "iot_class": "cloud_polling"
}
```

**Step 2: Validate JSON syntax**

Run: `python3 -c "import json; json.load(open('custom_components/ha_rt/manifest.json'))" && echo "JSON OK"`
Expected: `JSON OK`

---

## Task 9: Create HACS Metadata

**Files:**
- Create: `hacs.json`

**Step 1: Create hacs.json**

```json
{
  "name": "Service Management",
  "render_readme": true
}
```

**Step 2: Validate JSON syntax**

Run: `python3 -c "import json; json.load(open('hacs.json'))" && echo "JSON OK"`
Expected: `JSON OK`

---

## Task 10: Create README

**Files:**
- Create: `README.md`

**Step 1: Create README.md**

```markdown
# Service Management

Home Assistant integration for Request Tracker (RT) ticketing.

Automatically create and manage tickets based on Home Assistant events
with built-in deduplication.

## Features

- Create RT tickets from automations
- Automatic deduplication: comments on existing open tickets instead of creating duplicates
- Returns ticket URL for use in notifications

## Prerequisites

### Request Tracker Setup

Before installing this integration, configure your RT instance:

1. **API Token**
   - Create a service account in RT
   - Generate an API token with permissions to:
     - Create tickets
     - Search tickets
     - Add comments
   - Token format: RT REST2 API token

2. **Queue**
   - Create or identify the queue for tickets
   - Note the exact queue name (case-sensitive)

3. **Custom Field**
   - Create a ticket-level custom field named `DeviceId`
   - Type: Freeform text
   - Apply to your ticket queue
   - This field enables deduplication

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click "Integrations"
3. Click the three dots menu → "Custom repositories"
4. Add `https://github.com/USERNAME/ha_rt` as "Integration"
5. Search for "Service Management" and install
6. Restart Home Assistant

### Manual

1. Download the `custom_components/ha_rt` folder
2. Copy to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Service Management"
4. Enter:
   - RT Server URL (e.g., `https://rt.example.com`)
   - API Token
   - Queue Name

## Usage

### Service: ha_rt.create_ticket

Creates a new ticket or adds a comment to an existing open ticket.

| Parameter | Required | Description |
|-----------|----------|-------------|
| device_id | Yes | Unique identifier (e.g., entity_id) |
| subject | Yes | Ticket subject line |
| text | Yes | Ticket body or comment |

### Example Automation

```yaml
automation:
  - alias: "Create ticket on water leak"
    trigger:
      - platform: state
        entity_id: binary_sensor.water_leak
        to: "on"
    action:
      - service: ha_rt.create_ticket
        data:
          device_id: "{{ trigger.entity_id }}"
          subject: "Water leak detected"
          text: "Sensor {{ trigger.entity_id }} triggered at {{ now() }}"
        response_variable: ticket
      - service: notify.mobile_app
        data:
          title: "Ticket Created"
          message: "{{ ticket.ticket_url }}"
```

### Response Data

The service returns:

```json
{
  "ticket_id": 12345,
  "ticket_url": "https://rt.example.com/Ticket/Display.html?id=12345",
  "action": "created"
}
```

- `action`: Either `"created"` (new ticket) or `"commented"` (existing ticket)

## License

MIT License
```

**Step 2: Verify file exists**

Run: `head -5 README.md`
Expected: Shows first 5 lines of README

---

## Task 11: Create License File

**Files:**
- Create: `LICENSE`

**Step 1: Create MIT LICENSE**

```text
MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Step 2: Verify file exists**

Run: `head -3 LICENSE`
Expected: `MIT License`

---

## Task 12: Create GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/validate.yaml`

**Step 1: Create workflow directory and file**

```bash
mkdir -p .github/workflows
```

**Step 2: Create validate.yaml**

```yaml
name: Validate

on:
  push:
  pull_request:
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:

jobs:
  validate-hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: HACS Validation
        uses: hacs/action@main
        with:
          category: integration

  validate-hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Hassfest Validation
        uses: home-assistant/actions/hassfest@master
```

**Step 3: Verify file exists**

Run: `cat .github/workflows/validate.yaml`
Expected: Shows workflow content

---

## Task 13: Verify Complete Structure

**Step 1: List all files**

Run: `find . -type f -name "*.py" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.md" | grep -v __pycache__ | sort`

Expected files:
```
./.github/workflows/validate.yaml
./custom_components/ha_rt/__init__.py
./custom_components/ha_rt/config_flow.py
./custom_components/ha_rt/const.py
./custom_components/ha_rt/exceptions.py
./custom_components/ha_rt/manifest.json
./custom_components/ha_rt/rt_client.py
./custom_components/ha_rt/services.yaml
./custom_components/ha_rt/strings.json
./docs/plans/2026-01-04-hacs-integration-design.md
./docs/plans/2026-01-04-ha_rt-implementation.md
./hacs.json
./LICENSE
./README.md
./description.md
```

**Step 2: Verify Python syntax for all files**

Run: `python3 -m py_compile custom_components/ha_rt/*.py && echo "All Python files OK"`
Expected: `All Python files OK`

---

## Task 14: Initialize Git Repository

**Step 1: Initialize git**

```bash
git init
```

**Step 2: Create .gitignore**

```text
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.env
.venv
venv/
*.egg-info/
.eggs/
dist/
build/
.idea/
.vscode/
*.swp
*.swo
.DS_Store
```

**Step 3: Initial commit**

```bash
git add .
git commit -m "feat: initial ha_rt integration

HACS-compatible Home Assistant integration for Request Tracker (RT).

Features:
- Config flow with connection validation
- create_ticket service with deduplication
- Returns ticket URL and action taken

🤖 Generated with Claude Code"
```

---

## Summary

After completing all tasks, you will have:

- **12 files** in the integration
- HACS-compatible structure
- Config flow with RT connection validation
- `ha_rt.create_ticket` service with deduplication
- Complete documentation

**Next steps after implementation:**
1. Create GitHub repository
2. Push code
3. Test in Home Assistant dev environment
4. Create v1.0.0 release tag
5. Add to HACS as custom repository
