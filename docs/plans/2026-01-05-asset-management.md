# RT Asset Management Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create RT assets for Home Assistant devices and link tickets to those assets.

**Architecture:** When a ticket is created, first search for an existing asset by device_id. If not found, create one in the configured catalog. Then create the ticket and link it to the asset using RT's RefersTo relationship. Area and location info stays on the ticket (already implemented).

**Tech Stack:** Python, aiohttp, RT REST2 API

---

## Prerequisites

Before implementation, create in RT:
1. Asset catalog "HA Murten" (already done)
2. Asset custom field `DeviceId` (Freeform text) - for deduplication lookup

---

## Task 1: Add Asset Constants

**Files:**
- Modify: `custom_components/ha_rt/const.py`

**Step 1: Add new constants**

Add after line 17:

```python
CONF_CATALOG = "catalog"

# Defaults
DEFAULT_QUEUE = "Facility Management"
DEFAULT_CATALOG = "HA Murten"
```

And update the existing DEFAULT_QUEUE line placement.

**Step 2: Verify syntax**

Run: `python3 -m py_compile custom_components/ha_rt/const.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add custom_components/ha_rt/const.py
git commit -m "feat: add asset catalog constants"
```

---

## Task 2: Add Catalog to Config Flow

**Files:**
- Modify: `custom_components/ha_rt/config_flow.py`
- Modify: `custom_components/ha_rt/strings.json`

**Step 1: Update imports in config_flow.py**

Change line 13 from:
```python
from .const import CONF_ADDRESS, CONF_HA_URL, CONF_QUEUE, CONF_TOKEN, CONF_URL, DEFAULT_QUEUE, DOMAIN
```
to:
```python
from .const import CONF_ADDRESS, CONF_CATALOG, CONF_HA_URL, CONF_QUEUE, CONF_TOKEN, CONF_URL, DEFAULT_CATALOG, DEFAULT_QUEUE, DOMAIN
```

**Step 2: Add catalog to STEP_USER_DATA_SCHEMA**

Add after line 26 (`vol.Optional(CONF_ADDRESS, default=""): str,`):
```python
        vol.Required(CONF_CATALOG, default=DEFAULT_CATALOG): str,
```

**Step 3: Update strings.json - config section**

In the `config.step.user.data` object, add:
```json
"catalog": "Asset Catalog"
```

In the `config.step.user.data_description` object, add:
```json
"catalog": "RT asset catalog name for device assets."
```

**Step 4: Update strings.json - options section**

In `options.step.init.data`, add:
```json
"catalog": "Asset Catalog"
```

In `options.step.init.data_description`, add:
```json
"catalog": "RT asset catalog name for device assets."
```

**Step 5: Update HARTOptionsFlow to include catalog**

In `async_step_init`, update `new_data` dict to include:
```python
CONF_CATALOG: user_input[CONF_CATALOG],
```

Add after `current_address`:
```python
current_catalog = self.config_entry.data.get(CONF_CATALOG, DEFAULT_CATALOG)
```

Add to the form schema:
```python
vol.Required(CONF_CATALOG, default=current_catalog): str,
```

**Step 6: Verify syntax**

Run: `python3 -m py_compile custom_components/ha_rt/config_flow.py`
Expected: No output (success)

**Step 7: Commit**

```bash
git add custom_components/ha_rt/config_flow.py custom_components/ha_rt/strings.json
git commit -m "feat: add asset catalog configuration"
```

---

## Task 3: Add Asset Methods to RTClient

**Files:**
- Modify: `custom_components/ha_rt/rt_client.py`

**Step 1: Add search_asset method**

Add after `search_tickets` method (after line 91):

```python
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
```

**Step 2: Add create_asset method**

Add after `search_asset` method:

```python
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
```

**Step 3: Add link_ticket_to_asset method**

Add after `create_asset` method:

```python
    async def link_ticket_to_asset(self, ticket_id: int, asset_id: int) -> bool:
        """Link a ticket to an asset using RefersTo. Returns True on success."""
        # RT uses asset:// URI scheme for asset links
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
```

**Step 4: Verify syntax**

Run: `python3 -m py_compile custom_components/ha_rt/rt_client.py`
Expected: No output (success)

**Step 5: Commit**

```bash
git add custom_components/ha_rt/rt_client.py
git commit -m "feat: add asset search, create, and link methods"
```

---

## Task 4: Update __init__.py to Integrate Assets

**Files:**
- Modify: `custom_components/ha_rt/__init__.py`

**Step 1: Update imports**

Change line 17 from:
```python
from .const import CONF_ADDRESS, CONF_HA_URL, CONF_QUEUE, CONF_TOKEN, CONF_URL, DOMAIN
```
to:
```python
from .const import CONF_ADDRESS, CONF_CATALOG, CONF_HA_URL, CONF_QUEUE, CONF_TOKEN, CONF_URL, DEFAULT_CATALOG, DOMAIN
```

**Step 2: Add catalog to entry data storage**

In `async_setup_entry`, update the `hass.data[DOMAIN][entry.entry_id]` dict to add:
```python
"catalog": entry.data.get(CONF_CATALOG, DEFAULT_CATALOG),
```

**Step 3: Update handle_create_ticket to use assets**

After getting `entry_data` values, add:
```python
catalog: str = entry_data["catalog"]
```

After building `device_info_url`, add the asset logic:

```python
        # Get or create asset for this device
        asset_id = None
        if device_id:
            existing_asset = await rt_client.search_asset(catalog, device_id)
            if existing_asset:
                asset_id = existing_asset.get("id")
                _LOGGER.debug("Found existing asset: %s", asset_id)
            else:
                # Create new asset using device_id as name
                new_asset = await rt_client.create_asset(
                    catalog, device_id, device_id, device_info_url
                )
                if new_asset:
                    asset_id = new_asset.get("id")
                    _LOGGER.debug("Created new asset: %s", asset_id)
```

After creating a new ticket (inside the `else` block, after `action = "created"`), add:

```python
            # Link ticket to asset
            if asset_id:
                linked = await rt_client.link_ticket_to_asset(ticket_id, asset_id)
                if linked:
                    _LOGGER.debug("Linked ticket %s to asset %s", ticket_id, asset_id)
```

**Step 4: Verify syntax**

Run: `python3 -m py_compile custom_components/ha_rt/__init__.py`
Expected: No output (success)

**Step 5: Commit**

```bash
git add custom_components/ha_rt/__init__.py
git commit -m "feat: integrate asset management into ticket creation"
```

---

## Task 5: Update README Documentation

**Files:**
- Modify: `README.md`

**Step 1: Update Prerequisites - Custom Fields**

Add to the Custom Fields list:
```markdown
   - `DeviceId` (Freeform text) on **Assets** - enables asset lookup by device
```

**Step 2: Add Asset Catalog prerequisite**

Add after Custom Fields section:
```markdown
4. **Asset Catalog**
   - Create an asset catalog for Home Assistant devices
   - Note the exact catalog name (case-sensitive)
```

**Step 3: Update Configuration section**

Add to the "Enter:" list:
```markdown
   - Asset Catalog - RT catalog for device assets
```

**Step 4: Update ticket description**

Add to "The ticket will include:" list:
```markdown
- Linked to an RT asset representing the Home Assistant device
```

**Step 5: Add Assets section**

Add after "Deduplication Logic" section:
```markdown
## Asset Management

When `ha_rt.create_ticket` is called:

1. Searches for an existing asset with matching `device_id` in the configured catalog
2. If not found: creates a new asset using `device_id` as the asset name
3. Links the ticket to the asset using RT's RefersTo relationship

This enables:
- Tracking all tickets related to a specific device
- RT's asset management reporting capabilities
- Device lifecycle management alongside tickets
```

**Step 6: Commit**

```bash
git add README.md
git commit -m "docs: add asset management documentation"
```

---

## Task 6: Final Testing

**Step 1: Syntax check all files**

Run:
```bash
for f in custom_components/ha_rt/*.py; do python3 -m py_compile "$f" && echo "$f: OK"; done
```
Expected: All files report OK

**Step 2: Manual testing in Home Assistant**

1. Restart Home Assistant
2. Go to integration options, verify "Asset Catalog" field appears
3. Set catalog to "HA Murten"
4. Create a test ticket via automation or Developer Tools
5. Verify in RT:
   - Asset was created in "HA Murten" catalog
   - Asset has DeviceId custom field populated
   - Ticket has RefersTo link to the asset

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address testing feedback"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add asset constants | const.py |
| 2 | Add catalog to config flow | config_flow.py, strings.json |
| 3 | Add asset methods to RTClient | rt_client.py |
| 4 | Integrate assets in ticket creation | __init__.py |
| 5 | Update documentation | README.md |
| 6 | Final testing | All |
