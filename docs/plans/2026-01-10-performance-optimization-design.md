# Performance Optimization Design

## Overview

Optimize the ha_rt integration to reduce network request volume and improve sync performance for medium-sized Home Assistant installations (50-200 devices).

## Constraints

- RT server is shared; use conservative concurrency (max 5 concurrent requests)
- Ticket volume is low; per-ticket optimizations not needed
- Prefer hardcoded defaults over configuration complexity

## Changes

### 1. Add Concurrency Constant

**File:** `const.py`

Add `DEFAULT_CONCURRENCY_LIMIT = 5` as the bounded concurrency limit for parallel RT API calls.

### 2. Add Concurrency Helper

**File:** `asset_sync.py`

Add `run_with_concurrency(limit, tasks)` helper that runs async callables with a semaphore-based concurrency limit. Takes callables (not coroutines) to defer creation and avoid memory spikes.

```python
async def run_with_concurrency(
    limit: int,
    tasks: list[Callable[[], Coroutine[Any, Any, T]]],
) -> list[T]:
    semaphore = asyncio.Semaphore(limit)

    async def bounded(fn):
        async with semaphore:
            return await fn()

    return await asyncio.gather(*[bounded(fn) for fn in tasks])
```

### 3. Registry Passing in sync_device

**File:** `asset_sync.py`

Add optional `device_registry` and `area_registry` parameters to `sync_device()`. When called from bulk sync, registries are passed in. When called standalone, they're fetched internally. This eliminates redundant registry lookups in loops.

### 4. Parallel sync_all_devices

**File:** `asset_sync.py`

Refactor `sync_all_devices()` to:
1. Fetch registries once upfront
2. Build list of sync task callables
3. Run with `run_with_concurrency(5, tasks)`
4. Tally results from outcomes

Expected improvement: ~5x faster for 200 devices (40 batches of 5 vs 200 sequential).

### 5. Fix N+1 in cleanup_orphaned_assets

**File:** `asset_sync.py`

Refactor `cleanup_orphaned_assets()` to:
1. Fetch asset refs with `list_assets()` (single call)
2. Fetch full asset details concurrently with `run_with_concurrency()`
3. Identify orphans by checking device IDs against registry
4. Delete orphans concurrently with `run_with_concurrency()`

This eliminates the N+1 pattern where each asset required a separate `get_asset()` call.

### 6. Deduplicate Custom Field Logic

**File:** `rt_client.py`

Extract `_build_asset_custom_fields()` helper method used by both `create_asset()` and `update_asset()`. Single place to maintain field mappings.

## Files Modified

| File | Changes |
|------|---------|
| `const.py` | Add `DEFAULT_CONCURRENCY_LIMIT` |
| `asset_sync.py` | Add helper, refactor sync_all_devices, cleanup_orphaned_assets, sync_device |
| `rt_client.py` | Add `_build_asset_custom_fields()` helper |

## Not Included

- **Asset caching for ticket creation:** Low ticket volume (few per day) doesn't justify the complexity
- **Configurable concurrency:** Hardcoded default of 5 is appropriate for shared RT servers

## Testing

- Verify sync completes successfully with multiple devices
- Verify cleanup correctly identifies and deletes orphaned assets
- Verify single-device sync still works (event handler path)
- Monitor RT server load during sync to confirm concurrency limit is respected
