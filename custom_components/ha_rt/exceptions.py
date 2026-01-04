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
