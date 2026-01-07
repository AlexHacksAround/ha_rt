# Area and Address Asset Sync Design

## Goal

Sync device area and configured address into RT asset custom fields (Area and Address).

## Current State

- Asset sync handles device properties (name, manufacturer, model, etc.)
- `AREA_FIELD` and `ADDRESS_FIELD` constants exist
- Address is already configurable via `CONF_ADDRESS` in config flow
- Area information exists on devices via `area_id` linking to area registry

## Changes

### RT Client (`rt_client.py`)

Add `area` and `address` parameters to both `create_asset` and `update_asset`:

```python
async def create_asset(
    self,
    catalog: str,
    name: str,
    device_id: str,
    *,
    # ... existing params ...
    area: str = "",
    address: str = "",
) -> dict[str, Any] | None:
```

Populate custom fields when values provided:

```python
if area:
    custom_fields[AREA_FIELD] = area
if address:
    custom_fields[ADDRESS_FIELD] = address
```

### Asset Sync (`asset_sync.py`)

Modify `sync_device` signature:

```python
async def sync_device(
    hass: HomeAssistant,
    rt_client: RTClient,
    catalog: str,
    device_id: str,
    address: str = "",
) -> bool | None:
```

Look up area name from device's `area_id`:

```python
from homeassistant.helpers import area_registry as ar

area_name = ""
if device.area_id:
    area_registry = ar.async_get(hass)
    area = area_registry.async_get_area(device.area_id)
    if area:
        area_name = area.name
```

Pass both to RT client methods:

```python
await rt_client.create_asset(
    catalog, device_name, device_id,
    # ... existing fields ...
    area=area_name,
    address=address,
)
```

Modify `sync_all_devices` to accept and pass `address`:

```python
async def sync_all_devices(
    hass: HomeAssistant,
    rt_client: RTClient,
    catalog: str,
    cleanup: bool = True,
    address: str = "",
) -> dict[str, int]:
```

### Callers (`__init__.py`)

Pass address from config entry to all sync calls:

```python
address = entry.data.get(CONF_ADDRESS, "")

# Event handler
await sync_device(hass, rt_client, catalog, device_id, address=address)

# Scheduled sync
await sync_all_devices(hass, rt_client, catalog, address=address)

# Manual sync service
await sync_device(..., address=address)
await sync_all_devices(..., address=address)
```

## Files Changed

| File | Changes |
|------|---------|
| `rt_client.py` | Add `area` and `address` params to `create_asset` and `update_asset` |
| `asset_sync.py` | Look up area from registry, accept `address` param, pass both to RT client |
| `__init__.py` | Pass `address` from config to all sync callers |

## No Changes Needed

- Config flow - address already configurable
- Constants - `AREA_FIELD` and `ADDRESS_FIELD` already exist
