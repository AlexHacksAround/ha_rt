# Service Management

** This is experimental, do not download it or do so at your own risk **

Home Assistant integration for Request Tracker (RT) ticketing.

Automatically create and manage tickets based on Home Assistant events
with built-in deduplication.

## Features

- Create RT tickets from automations
- Automatic deduplication: comments on existing open tickets instead of creating duplicates
- Returns ticket URL for use in notifications
- Secure: HTTPS required, private networks blocked, input sanitization

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

3. **Custom Fields**
   - Create ticket-level custom fields and apply to your queue:
   - `DeviceId` (Freeform text) - enables deduplication
   - `Device Information` (Freeform text) - stores link to HA device page
   - `Area` (Freeform text) - stores the device's area/room in Home Assistant
   - `Address` (Freeform text) - stores the Home Assistant location address

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
   - Home Assistant URL (optional) - for device info links
   - Address (optional) - physical location of Home Assistant

**Note:** Only HTTPS URLs to public servers are allowed for security.

## Usage

### Service: ha_rt.create_ticket

Creates a new ticket or adds a comment to an existing open ticket.

| Parameter | Required | Description |
|-----------|----------|-------------|
| device_id | Yes | Home Assistant device registry ID |
| subject | Yes | Ticket subject line |
| text | Yes | Ticket body or comment |

Use the `device_id()` template function to get the registry ID from an entity:

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
          device_id: "{{ device_id(trigger.entity_id) }}"
          subject: "Water leak detected"
          text: "Sensor {{ trigger.entity_id }} triggered at {{ now() }}"
        response_variable: ticket
      - service: notify.mobile_app
        data:
          title: "Ticket Created"
          message: "{{ ticket.ticket_url }}"
```

The ticket will include:
- "Device Information" field with a direct link to the device in Home Assistant
- "Area" field with the device's assigned area (e.g., "Kitchen", "Garage")
- "Address" field with the configured location address
- Location and area info is also appended to the ticket body text

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

## Deduplication Logic

When `ha_rt.create_ticket` is called:

1. Searches for open tickets (status: new, open, stalled) with matching `device_id`
2. If found: adds comment to the first matching ticket
3. If not found: creates a new ticket

This prevents alert storms from flapping sensors.

## Security

This integration includes security measures:

- **HTTPS Required**: Only HTTPS URLs are accepted
- **SSRF Protection**: Private IPs, localhost, and cloud metadata endpoints are blocked
- **Input Sanitization**: All user input is escaped to prevent injection attacks

## Troubleshooting

### "Cannot connect to RT server"
- Verify the URL is correct and uses HTTPS
- Check that the RT server is accessible from Home Assistant
- Ensure the RT REST2 API is enabled

### "Invalid API token"
- Verify the token is correct
- Check that the token has sufficient permissions
- Ensure the token hasn't expired

### "Invalid or unsafe URL"
- Only HTTPS URLs to public servers are allowed
- Private IPs (192.168.x.x, 10.x.x.x, etc.) are blocked for security

## License

MIT License
