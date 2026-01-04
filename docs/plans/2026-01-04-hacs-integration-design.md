# Home Assistant RT Integration - HACS Design Session

## Overview

Transforming the existing Home Assistant → Request Tracker integration from `rest_command` based YAML configuration into a proper HACS-distributable custom integration.

---

## Decision Log

### Decision 1: Integration Domain Name

**Question:** What should the integration domain name be?

**Options presented:**
1. `rt` - Short and simple
2. `request_tracker` - More explicit
3. `ha_rt` - Matches current project name

**Decision:** `ha_rt`

**Rationale:** Maintains consistency with the existing project naming.

---

### Decision 2: Display Name

**Question:** What should the user-facing display name be?

**Options presented:**
1. "Request Tracker (RT)" - Full product name with abbreviation
2. "RT Ticketing" - Emphasizes the ticketing function
3. "Home Assistant RT" - Matches the domain name

**Decision:** "Service Management"

**Rationale:** Generic, professional name that describes the function rather than the backend system.

---

### Decision 3: Integration Scope

**Question:** What should the integration expose to Home Assistant?

**Options presented:**
1. Services only - Like now: `ha_rt.create_ticket`, `ha_rt.search_tickets`
2. Services + Sensor entity - Add open ticket count
3. Services + Event entity - Fire HA events for automations

**Decision:** Services only (option 1)

**Rationale:** Start simple, mirrors current behavior. Can extend later.

---

### Decision 4: Config Flow Fields

**Question:** What should the config flow (setup UI) collect?

**Options presented:**
1. Minimal: URL + Token only - Queue and custom field names hardcoded
2. URL + Token + Queue name - Let users pick queue during setup
3. URL + Token + Queue + DeviceId field name - Full flexibility

**Decision:** URL + Token + Queue Name

**Fields collected:**
- `url` - RT server URL
- `token` - API token
- `queue` - Queue name for ticket creation

**Future enhancement:** Query RT API for available queues and present as dropdown instead of text input.

**Documentation requirement:** README must clearly document RT-side prerequisites:
- API token with appropriate permissions
- A queue for ticket creation
- Custom field `DeviceId` on tickets for deduplication

---

### Decision 5: Service Design & Deduplication

**Question:** What services should the integration provide and where should deduplication logic live?

**Options presented:**
1. In automations - Separate search/create/comment services, automation handles logic
2. In the integration service - Single smart service handles dedup internally
3. Hybrid - Both low-level primitives and high-level convenience service

**Decision:** Option 2 - Integration handles deduplication internally

**Service behavior:**
- `ha_rt.create_ticket(device_id, subject, text)`
- Internally: searches for open ticket with matching `device_id`
- If no open ticket exists → create new ticket
- If open ticket exists → add comment to existing ticket

**Future enhancement:** Add `event_type` parameter for finer-grained deduplication:
- Dedup key becomes: `device_id` + `event_type`
- Allows multiple tickets per device for different event categories

**Rationale:** Centralizes logic in the integration, keeps automations simple, makes future changes easier.

---

### Decision 6: Service Response

**Question:** How should the service report its result?

**Options presented:**
1. Fire-and-forget - No feedback
2. Return response data - Ticket ID and action taken
3. Fire HA event - Emit events for other automations

**Decision:** Return response data with:
- `ticket_id` - The RT ticket number
- `ticket_url` - Full URL to access the ticket in RT web UI
- `action` - What was done ("created" or "commented")

**Example response:**
```json
{
  "ticket_id": 12345,
  "ticket_url": "https://rt.example.com/Ticket/Display.html?id=12345",
  "action": "created"
}
```

**Usage in automations:**
```yaml
action: ha_rt.create_ticket
data:
  device_id: "sensor.leak"
  subject: "Leak detected"
  text: "Water sensor triggered"
response_variable: ticket_response
```

---

### Decision 7: Error Handling

**Question:** How should errors be handled?

**Options presented:**
1. Raise exception - Service call fails, standard HA behavior
2. Return error in response - Service succeeds but with error field
3. Log and notify - Create persistent notification on failure

**Decision:** Option 1 - Raise exception

**Behavior:**
- API unreachable → `ServiceCallError` raised
- Invalid token / auth failure → `ServiceCallError` raised
- RT returns error → `ServiceCallError` raised

**Rationale:** Standard Home Assistant pattern. Automations can handle with `continue_on_error: true` if needed.

---

### Decision 8: Config Flow Validation

**Question:** Should setup validate the RT connection?

**Options presented:**
1. Validate immediately - Test API call during setup
2. Accept without validation - User discovers issues later

**Decision:** Option 1 - Validate during setup

**Behavior:**
- Config flow makes test API call to RT (e.g., simple query)
- Invalid URL → Show error "Cannot connect to RT server"
- Invalid token → Show error "Authentication failed"
- Success → Proceed with setup

**Rationale:** Better UX, catches typos and misconfigurations immediately.

---

### Decision 9: Repository Hosting

**Question:** Where will this integration be hosted?

**Options presented:**
1. Create new GitHub repo
2. Use current project location
3. Undecided

**Decision:** Option 1 - Create new GitHub repository

**Repository name:** `ha_rt` (or similar)

**Required for HACS:**
- Public GitHub repository
- Releases with version tags
- README with documentation

---

## Design

### Repository Structure

```
ha_rt/
├── .github/
│   └── workflows/
│       └── validate.yaml        # HACS validation workflow
├── custom_components/
│   └── ha_rt/
│       ├── __init__.py          # Integration setup, service registration
│       ├── manifest.json        # Integration metadata
│       ├── config_flow.py       # UI-based setup with validation
│       ├── strings.json         # UI text and translations
│       ├── services.yaml        # Service definitions for HA
│       └── rt_client.py         # RT REST2 API client
├── hacs.json                    # HACS metadata
├── README.md                    # User documentation + RT prerequisites
└── LICENSE                      # Open source license (MIT recommended)
```

### manifest.json

```json
{
  "domain": "ha_rt",
  "name": "Service Management",
  "version": "1.0.0",
  "documentation": "https://github.com/USERNAME/ha_rt",
  "issue_tracker": "https://github.com/USERNAME/ha_rt/issues",
  "codeowners": ["@USERNAME"],
  "dependencies": [],
  "requirements": ["aiohttp"],
  "config_flow": true,
  "integration_type": "service",
  "iot_class": "cloud_polling"
}
```

### hacs.json

```json
{
  "name": "Service Management",
  "render_readme": true
}
```

### Additional HACS Requirements

- **home-assistant/brands**: Must submit PR to add integration icon/logo (can be done after initial release)
- **GitHub Releases**: Use semantic versioning tags (v1.0.0) for HACS to track versions

### RT Client Design (rt_client.py)

Encapsulates all RT REST2 API communication.

```python
class RTClient:
    def __init__(self, session: aiohttp.ClientSession, url: str, token: str):
        self.session = session
        self.base_url = url.rstrip("/")
        self.token = token

    async def test_connection(self) -> bool:
        """Validate credentials. Used by config flow."""
        # GET /REST/2.0/user (returns current user info)

    async def search_tickets(self, queue: str, device_id: str) -> list[dict]:
        """Find open tickets for a device_id in a queue."""
        # TicketSQL: Queue="X" AND Status IN ("new","open","stalled") AND CF.{DeviceId}="Y"

    async def create_ticket(self, queue: str, subject: str, text: str, device_id: str) -> dict:
        """Create new ticket. Returns {id, url}."""
        # POST /REST/2.0/ticket

    async def add_comment(self, ticket_id: int, text: str) -> None:
        """Add comment to existing ticket."""
        # POST /REST/2.0/ticket/{id}/comment
```

**Error handling:**
- Connection errors → raise `CannotConnect`
- 401/403 responses → raise `InvalidAuth`
- Other API errors → raise `RTAPIError`

**Constants (hardcoded for v1):**
- `DEVICE_ID_FIELD = "DeviceId"`
- `OPEN_STATUSES = ["new", "open", "stalled"]`

**Configurable via config flow:**
- Queue name (stored in config entry)

### Config Flow Design (config_flow.py)

Single-step setup form that validates before saving.

```python
class HArtConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            try:
                client = RTClient(session, user_input["url"], user_input["token"])
                await client.test_connection()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(
                    title=f"Service Management ({user_input['queue']})",
                    data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("url"): str,
                vol.Required("token"): str,
                vol.Required("queue", default="Facility Management"): str,
            }),
            errors=errors
        )
```

**strings.json (UI text):**
```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to Request Tracker",
        "data": {
          "url": "RT Server URL",
          "token": "API Token",
          "queue": "Queue Name"
        }
      }
    },
    "error": {
      "cannot_connect": "Cannot connect to RT server",
      "invalid_auth": "Invalid API token"
    }
  }
}
```

**User experience:**
1. User adds integration via UI
2. Form shows: URL field, Token field, Queue Name (with default)
3. On submit: validates connection
4. Success → integration configured
5. Error → shows message, user can retry

### Service Implementation (__init__.py)

Registers the `ha_rt.create_ticket` service with built-in deduplication.

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Service Management from a config entry."""

    client = RTClient(
        session=async_get_clientsession(hass),
        url=entry.data["url"],
        token=entry.data["token"]
    )

    hass.data[DOMAIN] = {
        "client": client,
        "url": entry.data["url"],
        "queue": entry.data["queue"]
    }

    async def handle_create_ticket(call: ServiceCall) -> ServiceResponse:
        """Handle create_ticket service call with deduplication."""
        device_id = call.data["device_id"]
        subject = call.data["subject"]
        text = call.data["text"]

        queue = hass.data[DOMAIN]["queue"]

        # Search for existing open ticket
        existing = await client.search_tickets(queue, device_id)

        if existing:
            # Add comment to first open ticket
            ticket_id = existing[0]["id"]
            await client.add_comment(ticket_id, text)
            action = "commented"
        else:
            # Create new ticket
            result = await client.create_ticket(queue, subject, text, device_id)
            ticket_id = result["id"]
            action = "created"

        base_url = hass.data[DOMAIN]["url"].rstrip("/")
        ticket_url = f"{base_url}/Ticket/Display.html?id={ticket_id}"

        return {
            "ticket_id": ticket_id,
            "ticket_url": ticket_url,
            "action": action
        }

    hass.services.async_register(
        DOMAIN,
        "create_ticket",
        handle_create_ticket,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY
    )

    return True
```

**services.yaml:**
```yaml
create_ticket:
  name: Create or update ticket
  description: Creates a new ticket or comments on existing open ticket for the device
  fields:
    device_id:
      name: Device ID
      description: Unique identifier for the device/entity
      required: true
      example: "sensor.water_leak_kitchen"
      selector:
        text:
    subject:
      name: Subject
      description: Ticket subject line (used for new tickets)
      required: true
      example: "Water leak detected"
      selector:
        text:
    text:
      name: Text
      description: Ticket body or comment text
      required: true
      example: "Sensor triggered at 10:30 AM"
      selector:
        text:
          multiline: true
```

### README Documentation

The README.md must cover installation, RT prerequisites, and usage.

**Structure:**

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

- `action`: Either "created" (new ticket) or "commented" (existing ticket)
```

### Future Enhancements

Planned improvements for later versions:

1. **Queue selection dropdown** - Query RT API during config flow to list available queues
2. **Event type parameter** - Add `event_type` to service for finer deduplication (device_id + event_type)
3. **Configurable DeviceId field name** - Allow custom field name via options flow
4. **Sensor entities** - Show open ticket count per queue
5. **Auto-close tickets** - Service to resolve tickets when conditions clear

---

## Implementation Summary

**Files to create:**

| File | Purpose |
|------|---------|
| `custom_components/ha_rt/__init__.py` | Entry point, service registration |
| `custom_components/ha_rt/manifest.json` | Integration metadata |
| `custom_components/ha_rt/config_flow.py` | UI setup with validation |
| `custom_components/ha_rt/strings.json` | UI translations |
| `custom_components/ha_rt/services.yaml` | Service definitions |
| `custom_components/ha_rt/rt_client.py` | RT REST2 API client |
| `custom_components/ha_rt/const.py` | Constants (DOMAIN, etc.) |
| `custom_components/ha_rt/exceptions.py` | Custom exceptions |
| `hacs.json` | HACS metadata |
| `README.md` | User documentation |
| `.github/workflows/validate.yaml` | HACS validation |
| `LICENSE` | MIT license |

**Key behaviors:**
- Config flow collects URL, Token, Queue Name
- Validates RT connection before saving
- Single service `ha_rt.create_ticket` with built-in deduplication
- Returns ticket_id, ticket_url, action in response

---

## Status

**Design complete.** Ready for implementation.
