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
