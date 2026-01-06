# Asset Sync Design

## Goal

Separate asset management from ticket creation by adding dedicated asset sync functionality with event-driven, scheduled, and manual triggers.

## Architecture

**Current state:** Assets are created on-demand when `create_ticket` is called.

**New state:** Asset sync is a separate concern with three triggers:

1. **Event-driven** - Subscribe to `device_registry_updated` events. When a device is added, modified, or removed, sync that device to RT.

2. **Scheduled** - Run a full sync periodically (configurable interval, default 6 hours). Ensures RT stays in sync even if events were missed.

3. **Manual** - `ha_rt.sync_assets` service for on-demand bulk sync or single-device sync.

**Ticket creation changes:**
- Remove asset creation logic from `create_ticket`
- Keep asset lookup (search by DeviceId)
- If asset not found, log warning but still create ticket (graceful degradation)

## File Structure

```
custom_components/ha_rt/
├── __init__.py          # Setup, services, event subscriptions
├── asset_sync.py        # NEW: Asset sync logic
├── rt_client.py         # Add update_asset method
├── config_flow.py       # Add sync interval option
├── const.py             # Add new constants
├── strings.json         # Add sync service strings
└── ...

tests/
├── test_asset_sync.py   # NEW: Asset sync tests
├── test_rt_client.py    # NEW: RT client tests
└── ...
```

## Asset Sync Module (`asset_sync.py`)

### Functions

```python
async def sync_device(hass, rt_client, catalog, device_id) -> bool:
    """Sync a single device to RT. Returns True on success."""
    # Get device from registry
    # Extract all fields (name, manufacturer, model, etc.)
    # Search for existing asset by DeviceId
    # If exists: update asset
    # If not: create asset

async def sync_all_devices(hass, rt_client, catalog) -> dict:
    """Sync all devices. Returns {synced: N, failed: N, skipped: N}."""
    # Get all devices from registry
    # Call sync_device for each
    # Collect results

async def remove_asset(rt_client, catalog, device_id) -> bool:
    """Mark asset as deleted in RT when device is removed."""
    # Search for asset
    # If found: update status to deleted
```

### Tests

- `test_sync_device_creates_new_asset`
- `test_sync_device_updates_existing_asset`
- `test_sync_all_devices_handles_mixed_results`
- `test_sync_device_with_missing_fields`

## RT Client Changes

### New Method

```python
async def update_asset(self, asset_id, **fields) -> bool:
    """Update existing asset. PUT /REST/2.0/asset/{id}"""
```

## Event Subscription

In `async_setup_entry`:

```python
from homeassistant.helpers import device_registry as dr

async def handle_device_event(event):
    """Handle device added/updated/removed."""
    action = event.data.get("action")
    device_id = event.data.get("device_id")

    if action in ("create", "update"):
        await sync_device(hass, rt_client, catalog, device_id)
    elif action == "remove":
        await remove_asset(rt_client, catalog, device_id)

entry.async_on_unload(
    hass.bus.async_listen("device_registry_updated", handle_device_event)
)
```

### Tests

- `test_device_create_event_triggers_sync`
- `test_device_update_event_triggers_sync`
- `test_device_remove_event_triggers_removal`

## Scheduled Sync

```python
from homeassistant.helpers.event import async_track_time_interval

async def scheduled_sync(now):
    """Run periodic full sync."""
    await sync_all_devices(hass, rt_client, catalog)

entry.async_on_unload(
    async_track_time_interval(hass, scheduled_sync, timedelta(hours=sync_interval))
)
```

**Config option:** Add `sync_interval` (hours) to config flow, default 6.

### Tests

- `test_scheduled_sync_runs_at_interval`

## Manual Sync Service

### Service Definition

```python
SERVICE_SYNC_ASSETS = "sync_assets"

SYNC_SCHEMA = vol.Schema({
    vol.Optional("device_id"): cv.string,
})
```

### Handler

```python
async def handle_sync_assets(call: ServiceCall) -> ServiceResponse:
    device_id = call.data.get("device_id")

    if device_id:
        success = await sync_device(hass, rt_client, catalog, device_id)
        return {"synced": 1 if success else 0, "failed": 0 if success else 1}
    else:
        return await sync_all_devices(hass, rt_client, catalog)
```

### Response

```json
{"synced": 42, "failed": 2, "skipped": 0}
```

### strings.json

```json
"sync_assets": {
  "name": "Sync assets",
  "description": "Sync Home Assistant devices to RT assets.",
  "fields": {
    "device_id": {
      "name": "Device ID",
      "description": "Optional. Sync single device, or omit for full sync."
    }
  }
}
```

### Tests

- `test_sync_service_full_sync`
- `test_sync_service_single_device`
- `test_sync_service_returns_counts`

## Ticket Creation Changes

Remove asset creation, keep lookup:

```python
# Get asset for this device (should already exist from sync)
asset_id = None
if device_id:
    existing_asset = await rt_client.search_asset(catalog, device_id)
    if existing_asset:
        asset_id = existing_asset.get("id")
    else:
        _LOGGER.warning(
            "Asset not found for device %s. Run sync_assets service.", device_id
        )

# Rest of ticket logic unchanged...
```

### Tests

- `test_create_ticket_with_existing_asset`
- `test_create_ticket_without_asset_logs_warning`
- `test_create_ticket_still_works_without_asset`

## Error Handling

### Full Sync

Individual failures don't stop the sync:

```python
async def sync_all_devices(hass, rt_client, catalog) -> dict:
    results = {"synced": 0, "failed": 0, "skipped": 0}

    for device in device_registry.devices.values():
        try:
            success = await sync_device(hass, rt_client, catalog, device.id)
            results["synced" if success else "failed"] += 1
        except Exception as err:
            _LOGGER.error("Failed to sync device %s: %s", device.id, err)
            results["failed"] += 1

    return results
```

### Event Handler

Exceptions are caught and logged, never re-raised:

```python
async def handle_device_event(event):
    try:
        # ... sync logic ...
    except Exception as err:
        _LOGGER.error("Device event handler failed: %s", err)
```

### Tests

- `test_sync_all_continues_after_single_failure`
- `test_event_handler_catches_exceptions`
- `test_sync_logs_summary`

## Summary

| Component | Changes |
|-----------|---------|
| `asset_sync.py` | NEW - sync logic |
| `rt_client.py` | Add `update_asset` method |
| `__init__.py` | Event subscription, scheduled sync, new service, remove asset creation from ticket flow |
| `config_flow.py` | Add `sync_interval` option |
| `strings.json` | Add `sync_assets` service strings |
| `const.py` | Add new constants |
| `tests/` | NEW - comprehensive test coverage |
