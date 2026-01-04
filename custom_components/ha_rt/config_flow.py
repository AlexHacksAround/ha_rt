"""Config flow for Service Management integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_QUEUE, CONF_TOKEN, CONF_URL, DEFAULT_QUEUE, DOMAIN
from .exceptions import CannotConnect, InvalidAuth, RTAPIError
from .rt_client import RTClient
from .validators import InvalidURL, validate_rt_url

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_QUEUE, default=DEFAULT_QUEUE): str,
    }
)


class HARTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Service Management."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate URL first to prevent SSRF
                validate_rt_url(user_input[CONF_URL])

                session = async_get_clientsession(self.hass)
                client = RTClient(
                    session=session,
                    url=user_input[CONF_URL],
                    token=user_input[CONF_TOKEN],
                )
                await client.test_connection()
            except InvalidURL as err:
                _LOGGER.warning("Invalid URL: %s", err)
                errors["base"] = "invalid_url"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except RTAPIError as err:
                _LOGGER.warning("RT API error: %s", err)
                errors["base"] = "api_error"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                title = f"Service Management ({user_input[CONF_QUEUE]})"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
