# Asset Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add dedicated asset sync functionality with event-driven, scheduled, and manual triggers, separating asset management from ticket creation.

**Architecture:** New `asset_sync.py` module handles sync logic. Event subscriptions and scheduled tasks in `__init__.py`. New `update_asset` method in `rt_client.py`. Ticket creation simplified to asset lookup only.

**Tech Stack:** Python, aiohttp, Home Assistant (device_registry, event bus, async_track_time_interval), pytest

---

## Task 1: Set Up Test Infrastructure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create tests directory and init file**

```python
# tests/__init__.py
"""Tests for ha_rt integration."""
```

**Step 2: Create pytest fixtures**

```python
# tests/conftest.py
"""Pytest fixtures for ha_rt tests."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.fixture
def mock_rt_client():
    """Create a mock RT client."""
    client = AsyncMock()
    client.search_asset = AsyncMock(return_value=None)
    client.create_asset = AsyncMock(return_value={"id": 123})
    client.update_asset = AsyncMock(return_value=True)
    client.search_tickets_for_asset = AsyncMock(return_value=[])
    client.create_ticket = AsyncMock(return_value={"id": 456})
    client.add_comment = AsyncMock(return_value=None)
    client.link_ticket_to_asset = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_device():
    """Create a mock device registry entry."""
    device = MagicMock()
    device.id = "test-device-id-123"
    device.name = "Test Device"
    device.name_by_user = None
    device.manufacturer = "Test Manufacturer"
    device.model = "Test Model"
    device.serial_number = "SN123"
    device.sw_version = "1.0.0"
    device.hw_version = "2.0"
    device.configuration_url = "http://192.168.1.100"
    device.connections = {("mac", "aa:bb:cc:dd:ee:ff")}
    device.area_id = None
    return device


@pytest.fixture
def mock_device_registry(mock_device):
    """Create a mock device registry."""
    registry = MagicMock()
    registry.devices = MagicMock()
    registry.devices.values.return_value = [mock_device]
    registry.async_get.return_value = mock_device
    return registry


@pytest.fixture
def mock_hass(mock_device_registry):
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=mock_device_registry
    ):
        yield hass
```

**Step 3: Verify pytest can find tests**

Run: `cd /var/www/playground/ha_rt && python3 -m pytest tests/ --collect-only`
Expected: Shows collected 0 items (no tests yet, but no errors)

**Step 4: Commit**

```bash
git add tests/
git commit -m "test: set up pytest infrastructure"
```

---

## Task 2: Add update_asset Method to RT Client

**Files:**
- Modify: `custom_components/ha_rt/rt_client.py`
- Create: `tests/test_rt_client.py`

**Step 1: Write the failing test**

```python
# tests/test_rt_client.py
"""Tests for RT client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientSession

from custom_components.ha_rt.rt_client import RTClient


@pytest.fixture
def rt_client():
    """Create RT client with mocked session."""
    session = AsyncMock(spec=ClientSession)
    return RTClient(session=session, url="https://rt.example.com", token="test-token")


@pytest.mark.asyncio
async def test_update_asset_success(rt_client):
    """Test successful asset update."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    rt_client.session.put = MagicMock(return_value=mock_response)

    result = await rt_client.update_asset(
        asset_id=123,
        name="Updated Name",
        manufacturer="New Manufacturer"
    )

    assert result is True
    rt_client.session.put.assert_called_once()
    call_args = rt_client.session.put.call_args
    assert "123" in call_args[0][0]  # URL contains asset ID


@pytest.mark.asyncio
async def test_update_asset_failure(rt_client):
    """Test asset update failure."""
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value="Bad request")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    rt_client.session.put = MagicMock(return_value=mock_response)

    result = await rt_client.update_asset(asset_id=123, name="Test")

    assert result is False
```

**Step 2: Run test to verify it fails**

Run: `cd /var/www/playground/ha_rt && python3 -m pytest tests/test_rt_client.py -v`
Expected: FAIL with "AttributeError: 'RTClient' object has no attribute 'update_asset'"

**Step 3: Write minimal implementation**

Add after `create_asset` method in `rt_client.py`:

```python
    async def update_asset(
        self,
        asset_id: int,
        *,
        name: str = "",
        manufacturer: str = "",
        model: str = "",
        serial_number: str = "",
        sw_version: str = "",
        hw_version: str = "",
        config_url: str = "",
        mac_address: str = "",
    ) -> bool:
        """Update an existing asset. Returns True on success."""
        custom_fields: dict[str, str] = {}
        if manufacturer:
            custom_fields[ASSET_MANUFACTURER_FIELD] = manufacturer
        if model:
            custom_fields[ASSET_MODEL_FIELD] = model
        if serial_number:
            custom_fields[ASSET_SERIAL_FIELD] = serial_number
        if sw_version:
            custom_fields[ASSET_FIRMWARE_FIELD] = sw_version
        if hw_version:
            custom_fields[ASSET_HARDWARE_FIELD] = hw_version
        if config_url:
            custom_fields[ASSET_CONFIG_URL_FIELD] = config_url
        if mac_address:
            custom_fields[ASSET_MAC_FIELD] = mac_address

        payload: dict[str, Any] = {}
        if name:
            payload["Name"] = name
        if custom_fields:
            payload["CustomFields"] = custom_fields

        if not payload:
            return True  # Nothing to update

        try:
            async with self.session.put(
                f"{self.base_url}/REST/2.0/asset/{asset_id}",
                headers=self._headers(),
                json=payload,
            ) as response:
                if response.status not in (200, 201):
                    resp_text = await response.text()
                    _LOGGER.warning("Asset update failed: %s - %s", response.status, resp_text)
                    return False
                return True
        except ClientError as err:
            _LOGGER.warning("Asset update error: %s", err)
            return False
```

**Step 4: Run test to verify it passes**

Run: `cd /var/www/playground/ha_rt && python3 -m pytest tests/test_rt_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add custom_components/ha_rt/rt_client.py tests/test_rt_client.py
git commit -m "feat: add update_asset method to RT client"
```

---

## Task 3: Create Asset Sync Module - sync_device Function

**Files:**
- Create: `custom_components/ha_rt/asset_sync.py`
- Create: `tests/test_asset_sync.py`

**Step 1: Write the failing test for creating new asset**

```python
# tests/test_asset_sync.py
"""Tests for asset sync module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_sync_device_creates_new_asset():
    """Test sync_device creates asset when none exists."""
    from custom_components.ha_rt.asset_sync import sync_device

    mock_rt_client = AsyncMock()
    mock_rt_client.search_asset = AsyncMock(return_value=None)
    mock_rt_client.create_asset = AsyncMock(return_value={"id": 123})

    mock_device = MagicMock()
    mock_device.id = "device-123"
    mock_device.name = "Test Device"
    mock_device.name_by_user = None
    mock_device.manufacturer = "Acme"
    mock_device.model = "Widget"
    mock_device.serial_number = "SN001"
    mock_device.sw_version = "1.0"
    mock_device.hw_version = "2.0"
    mock_device.configuration_url = None
    mock_device.connections = set()

    mock_registry = MagicMock()
    mock_registry.async_get.return_value = mock_device

    mock_hass = MagicMock()

    with patch(
        "custom_components.ha_rt.asset_sync.dr.async_get",
        return_value=mock_registry
    ):
        result = await sync_device(mock_hass, mock_rt_client, "TestCatalog", "device-123")

    assert result is True
    mock_rt_client.create_asset.assert_called_once()
    call_kwargs = mock_rt_client.create_asset.call_args
    assert call_kwargs[0][0] == "TestCatalog"
    assert call_kwargs[0][1] == "Test Device"
```

**Step 2: Run test to verify it fails**

Run: `cd /var/www/playground/ha_rt && python3 -m pytest tests/test_asset_sync.py::test_sync_device_creates_new_asset -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

**Step 3: Write minimal implementation**

```python
# custom_components/ha_rt/asset_sync.py
"""Asset synchronization between Home Assistant and RT."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .rt_client import RTClient

_LOGGER = logging.getLogger(__name__)


async def sync_device(
    hass: HomeAssistant,
    rt_client: RTClient,
    catalog: str,
    device_id: str,
) -> bool:
    """Sync a single device to RT. Returns True on success."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if not device:
        _LOGGER.warning("Device not found: %s", device_id)
        return False

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
        )
        if new_asset:
            _LOGGER.debug("Created asset %s for device %s", new_asset.get("id"), device_id)
            return True
        return False
```

**Step 4: Run test to verify it passes**

Run: `cd /var/www/playground/ha_rt && python3 -m pytest tests/test_asset_sync.py::test_sync_device_creates_new_asset -v`
Expected: PASS

**Step 5: Commit**

```bash
git add custom_components/ha_rt/asset_sync.py tests/test_asset_sync.py
git commit -m "feat: add sync_device function"
```

---

## Task 4: Add Test for sync_device Updates Existing Asset

**Files:**
- Modify: `tests/test_asset_sync.py`

**Step 1: Write the test**

```python
@pytest.mark.asyncio
async def test_sync_device_updates_existing_asset():
    """Test sync_device updates asset when it exists."""
    from custom_components.ha_rt.asset_sync import sync_device

    mock_rt_client = AsyncMock()
    mock_rt_client.search_asset = AsyncMock(return_value={"id": 456})
    mock_rt_client.update_asset = AsyncMock(return_value=True)

    mock_device = MagicMock()
    mock_device.id = "device-123"
    mock_device.name = "Updated Device"
    mock_device.name_by_user = "My Custom Name"
    mock_device.manufacturer = "Acme"
    mock_device.model = "Widget Pro"
    mock_device.serial_number = None
    mock_device.sw_version = "2.0"
    mock_device.hw_version = None
    mock_device.configuration_url = None
    mock_device.connections = set()

    mock_registry = MagicMock()
    mock_registry.async_get.return_value = mock_device

    mock_hass = MagicMock()

    with patch(
        "custom_components.ha_rt.asset_sync.dr.async_get",
        return_value=mock_registry
    ):
        result = await sync_device(mock_hass, mock_rt_client, "TestCatalog", "device-123")

    assert result is True
    mock_rt_client.update_asset.assert_called_once()
    call_kwargs = mock_rt_client.update_asset.call_args
    assert call_kwargs[0][0] == 456  # asset_id
    assert call_kwargs[1]["name"] == "My Custom Name"  # Uses name_by_user
```

**Step 2: Run test to verify it passes**

Run: `cd /var/www/playground/ha_rt && python3 -m pytest tests/test_asset_sync.py::test_sync_device_updates_existing_asset -v`
Expected: PASS (implementation already handles this)

**Step 3: Commit**

```bash
git add tests/test_asset_sync.py
git commit -m "test: add test for sync_device update path"
```

---

## Task 5: Add sync_all_devices Function

**Files:**
- Modify: `custom_components/ha_rt/asset_sync.py`
- Modify: `tests/test_asset_sync.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_sync_all_devices():
    """Test sync_all_devices syncs all devices."""
    from custom_components.ha_rt.asset_sync import sync_all_devices

    mock_rt_client = AsyncMock()
    mock_rt_client.search_asset = AsyncMock(return_value=None)
    mock_rt_client.create_asset = AsyncMock(return_value={"id": 123})

    mock_device1 = MagicMock()
    mock_device1.id = "device-1"
    mock_device1.name = "Device 1"
    mock_device1.name_by_user = None
    mock_device1.manufacturer = ""
    mock_device1.model = ""
    mock_device1.serial_number = None
    mock_device1.sw_version = None
    mock_device1.hw_version = None
    mock_device1.configuration_url = None
    mock_device1.connections = set()

    mock_device2 = MagicMock()
    mock_device2.id = "device-2"
    mock_device2.name = "Device 2"
    mock_device2.name_by_user = None
    mock_device2.manufacturer = ""
    mock_device2.model = ""
    mock_device2.serial_number = None
    mock_device2.sw_version = None
    mock_device2.hw_version = None
    mock_device2.configuration_url = None
    mock_device2.connections = set()

    mock_registry = MagicMock()
    mock_registry.devices.values.return_value = [mock_device1, mock_device2]
    mock_registry.async_get.side_effect = lambda did: mock_device1 if did == "device-1" else mock_device2

    mock_hass = MagicMock()

    with patch(
        "custom_components.ha_rt.asset_sync.dr.async_get",
        return_value=mock_registry
    ):
        result = await sync_all_devices(mock_hass, mock_rt_client, "TestCatalog")

    assert result["synced"] == 2
    assert result["failed"] == 0
    assert mock_rt_client.create_asset.call_count == 2
```

**Step 2: Run test to verify it fails**

Run: `cd /var/www/playground/ha_rt && python3 -m pytest tests/test_asset_sync.py::test_sync_all_devices -v`
Expected: FAIL with "ImportError" (sync_all_devices doesn't exist)

**Step 3: Write minimal implementation**

Add to `asset_sync.py`:

```python
async def sync_all_devices(
    hass: HomeAssistant,
    rt_client: RTClient,
    catalog: str,
) -> dict[str, int]:
    """Sync all devices to RT. Returns counts of synced/failed."""
    results = {"synced": 0, "failed": 0}
    device_registry = dr.async_get(hass)

    for device in device_registry.devices.values():
        try:
            success = await sync_device(hass, rt_client, catalog, device.id)
            if success:
                results["synced"] += 1
            else:
                results["failed"] += 1
        except Exception as err:
            _LOGGER.error("Failed to sync device %s: %s", device.id, err)
            results["failed"] += 1

    _LOGGER.info(
        "Asset sync complete: %d synced, %d failed",
        results["synced"],
        results["failed"],
    )
    return results
```

**Step 4: Run test to verify it passes**

Run: `cd /var/www/playground/ha_rt && python3 -m pytest tests/test_asset_sync.py::test_sync_all_devices -v`
Expected: PASS

**Step 5: Commit**

```bash
git add custom_components/ha_rt/asset_sync.py tests/test_asset_sync.py
git commit -m "feat: add sync_all_devices function"
```

---

## Task 6: Add sync_all_devices Error Handling Test

**Files:**
- Modify: `tests/test_asset_sync.py`

**Step 1: Write the test**

```python
@pytest.mark.asyncio
async def test_sync_all_continues_after_failure():
    """Test sync_all_devices continues when one device fails."""
    from custom_components.ha_rt.asset_sync import sync_all_devices

    mock_rt_client = AsyncMock()
    # First call fails, second succeeds
    mock_rt_client.search_asset = AsyncMock(return_value=None)
    mock_rt_client.create_asset = AsyncMock(side_effect=[None, {"id": 123}])

    mock_device1 = MagicMock()
    mock_device1.id = "device-1"
    mock_device1.name = "Device 1"
    mock_device1.name_by_user = None
    mock_device1.manufacturer = ""
    mock_device1.model = ""
    mock_device1.serial_number = None
    mock_device1.sw_version = None
    mock_device1.hw_version = None
    mock_device1.configuration_url = None
    mock_device1.connections = set()

    mock_device2 = MagicMock()
    mock_device2.id = "device-2"
    mock_device2.name = "Device 2"
    mock_device2.name_by_user = None
    mock_device2.manufacturer = ""
    mock_device2.model = ""
    mock_device2.serial_number = None
    mock_device2.sw_version = None
    mock_device2.hw_version = None
    mock_device2.configuration_url = None
    mock_device2.connections = set()

    mock_registry = MagicMock()
    mock_registry.devices.values.return_value = [mock_device1, mock_device2]
    mock_registry.async_get.side_effect = lambda did: mock_device1 if did == "device-1" else mock_device2

    mock_hass = MagicMock()

    with patch(
        "custom_components.ha_rt.asset_sync.dr.async_get",
        return_value=mock_registry
    ):
        result = await sync_all_devices(mock_hass, mock_rt_client, "TestCatalog")

    assert result["synced"] == 1
    assert result["failed"] == 1
    assert mock_rt_client.create_asset.call_count == 2  # Both were attempted
```

**Step 2: Run test to verify it passes**

Run: `cd /var/www/playground/ha_rt && python3 -m pytest tests/test_asset_sync.py::test_sync_all_continues_after_failure -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_asset_sync.py
git commit -m "test: add error handling test for sync_all_devices"
```

---

## Task 7: Add sync_assets Service

**Files:**
- Modify: `custom_components/ha_rt/const.py`
- Modify: `custom_components/ha_rt/strings.json`
- Modify: `custom_components/ha_rt/__init__.py`

**Step 1: Add constants**

Add to `const.py`:

```python
SERVICE_SYNC_ASSETS = "sync_assets"
```

**Step 2: Add strings**

Add to `strings.json` in the `services` section:

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

**Step 3: Add service registration**

Add to `__init__.py` after existing service registration:

```python
from .asset_sync import sync_device, sync_all_devices

SERVICE_SYNC_ASSETS = "sync_assets"

SYNC_SCHEMA = vol.Schema({
    vol.Optional("device_id"): cv.string,
})

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
    SERVICE_SYNC_ASSETS,
    handle_sync_assets,
    schema=SYNC_SCHEMA,
    supports_response=SupportsResponse.ONLY,
)
```

**Step 4: Verify syntax**

Run: `python3 -m py_compile custom_components/ha_rt/__init__.py`
Expected: No output (success)

**Step 5: Commit**

```bash
git add custom_components/ha_rt/const.py custom_components/ha_rt/strings.json custom_components/ha_rt/__init__.py
git commit -m "feat: add sync_assets service"
```

---

## Task 8: Add Event Subscription for Device Changes

**Files:**
- Modify: `custom_components/ha_rt/__init__.py`

**Step 1: Add event handler**

Add to `async_setup_entry` after service registration:

```python
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
    except Exception as err:
        _LOGGER.error("Failed to sync device %s: %s", device_id, err)

entry.async_on_unload(
    hass.bus.async_listen("device_registry_updated", handle_device_registry_event)
)
```

**Step 2: Verify syntax**

Run: `python3 -m py_compile custom_components/ha_rt/__init__.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add custom_components/ha_rt/__init__.py
git commit -m "feat: add event-driven asset sync on device changes"
```

---

## Task 9: Add Scheduled Sync

**Files:**
- Modify: `custom_components/ha_rt/const.py`
- Modify: `custom_components/ha_rt/config_flow.py`
- Modify: `custom_components/ha_rt/strings.json`
- Modify: `custom_components/ha_rt/__init__.py`

**Step 1: Add constant and default**

Add to `const.py`:

```python
CONF_SYNC_INTERVAL = "sync_interval"
DEFAULT_SYNC_INTERVAL = 6  # hours
```

**Step 2: Update config flow**

Add to imports in `config_flow.py`:
```python
from .const import CONF_ADDRESS, CONF_CATALOG, CONF_HA_URL, CONF_QUEUE, CONF_SYNC_INTERVAL, CONF_TOKEN, CONF_URL, DEFAULT_CATALOG, DEFAULT_QUEUE, DEFAULT_SYNC_INTERVAL, DOMAIN
```

Add to `STEP_USER_DATA_SCHEMA`:
```python
vol.Optional(CONF_SYNC_INTERVAL, default=DEFAULT_SYNC_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
```

Add to options flow schema and handling similarly.

**Step 3: Update strings.json**

Add to `config.step.user.data`:
```json
"sync_interval": "Sync Interval (hours)"
```

Add to `config.step.user.data_description`:
```json
"sync_interval": "How often to sync all devices to RT assets (1-24 hours)."
```

**Step 4: Add scheduled sync to __init__.py**

Add import:
```python
from datetime import timedelta
from homeassistant.helpers.event import async_track_time_interval
```

Add to `async_setup_entry` after event subscription:

```python
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
```

**Step 5: Update entry data storage**

Add to entry data dict:
```python
"sync_interval": entry.data.get(CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL),
```

**Step 6: Verify syntax**

Run: `python3 -m py_compile custom_components/ha_rt/__init__.py custom_components/ha_rt/config_flow.py`
Expected: No output (success)

**Step 7: Commit**

```bash
git add custom_components/ha_rt/const.py custom_components/ha_rt/config_flow.py custom_components/ha_rt/strings.json custom_components/ha_rt/__init__.py
git commit -m "feat: add scheduled asset sync"
```

---

## Task 10: Simplify Ticket Creation - Remove Asset Creation

**Files:**
- Modify: `custom_components/ha_rt/__init__.py`

**Step 1: Update handle_create_ticket**

Replace the asset creation block with lookup-only:

```python
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
```

Remove all the device info extraction that was only used for asset creation (manufacturer, model, etc.) - keep only what's needed for tickets.

**Step 2: Verify syntax**

Run: `python3 -m py_compile custom_components/ha_rt/__init__.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add custom_components/ha_rt/__init__.py
git commit -m "refactor: simplify ticket creation to asset lookup only"
```

---

## Task 11: Update README

**Files:**
- Modify: `README.md`

**Step 1: Add Asset Sync section**

Add after Configuration section:

```markdown
## Asset Synchronization

The integration keeps RT assets in sync with Home Assistant devices:

### Automatic Sync

- **On device changes**: When devices are added or updated in Home Assistant
- **Scheduled**: Full sync runs every N hours (configurable, default 6)

### Manual Sync

```yaml
# Sync all devices
action: ha_rt.sync_assets

# Sync single device
action: ha_rt.sync_assets
data:
  device_id: "abc123"
```

### Response

```json
{"synced": 42, "failed": 2}
```
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add asset sync documentation"
```

---

## Task 12: Run All Tests and Final Verification

**Step 1: Run all tests**

Run: `cd /var/www/playground/ha_rt && python3 -m pytest tests/ -v`
Expected: All tests PASS

**Step 2: Syntax check all files**

Run: `for f in custom_components/ha_rt/*.py; do python3 -m py_compile "$f" && echo "$f: OK"; done`
Expected: All files OK

**Step 3: Final commit if needed**

```bash
git add -A
git commit -m "chore: final cleanup" --allow-empty
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Set up test infrastructure |
| 2 | Add update_asset to RT client |
| 3 | Create sync_device function |
| 4 | Add test for update path |
| 5 | Add sync_all_devices function |
| 6 | Add error handling test |
| 7 | Add sync_assets service |
| 8 | Add event subscription |
| 9 | Add scheduled sync |
| 10 | Simplify ticket creation |
| 11 | Update README |
| 12 | Final verification |
