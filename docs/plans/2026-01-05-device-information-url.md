# Device Information URL Feature

## Overview

Add a "Device Information" custom field to RT tickets containing a direct link to the Home Assistant device page.

## Service Parameter Changes

The `create_ticket` service keeps its current parameters but with updated semantics:

| Parameter | Type | Description |
|-----------|------|-------------|
| `device_id` | string | HA device registry ID (e.g., `4e44822107eb214b9065fb0cc7148bac`) |
| `subject` | string | Ticket subject line |
| `text` | string | Ticket body/comment |

Example automation usage:

```yaml
action:
  - service: ha_rt.create_ticket
    data:
      device_id: "{{ device_id(trigger.entity_id) }}"
      subject: "Water leak detected"
      text: "Sensor triggered at {{ now() }}"
```

The `device_id()` template function converts an entity_id to its device registry ID.

**Breaking change**: This changes the expected format of `device_id` from entity_id to device registry ID.

## Device Information URL Construction

**Getting the HA base URL:**

Use `get_url()` from `homeassistant.helpers.network`. Returns configured external URL (preferred) or internal URL as fallback.

**URL format:**
```
{ha_base_url}/config/devices/device/{device_id}
```

**Graceful fallback logic:**

1. If `device_id` is provided and non-empty: construct full URL
2. If `device_id` is empty/None: set Device Information to empty string
3. If `get_url()` fails (no URL configured): set Device Information to empty string, log warning

Ticket still gets created in all cases.

## RT API Changes

The `create_ticket` method accepts optional `device_info_url` parameter:

```python
payload = {
    "Queue": queue,
    "Subject": subject,
    "Content": text,
    "CustomFields": {
        "DeviceId": device_id,
        "Device Information": device_info_url,
    },
}
```

Omit `Device Information` from payload when empty.

## Integration Logic

```python
from homeassistant.helpers.network import get_url, NoURLAvailableError

async def handle_create_ticket(call: ServiceCall) -> ServiceResponse:
    device_id = call.data["device_id"]

    # Build device info URL
    device_info_url = ""
    if device_id:
        try:
            ha_url = get_url(hass)
            device_info_url = f"{ha_url}/config/devices/device/{device_id}"
        except NoURLAvailableError:
            _LOGGER.warning("No HA URL configured, skipping Device Information")

    # Pass device_info_url to create_ticket()
```

No validation of device_id format - caller's responsibility.

## Files to Modify

| File | Changes |
|------|---------|
| `const.py` | Add `DEVICE_INFO_FIELD = "Device Information"` |
| `rt_client.py` | Update `create_ticket()` to accept optional `device_info_url` parameter |
| `__init__.py` | Build device URL using `get_url()`, pass to `create_ticket()` |
| `README.md` | Update docs for device registry ID, add `device_id()` template example |
| `services.yaml` | Update parameter description |

## Version

v1.1.0 (minor version - new feature)
