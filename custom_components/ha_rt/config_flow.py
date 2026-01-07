"""Config flow for Service Management integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ADDRESS, CONF_CATALOG, CONF_HA_URL, CONF_QUEUE, CONF_SYNC_INTERVAL, CONF_TOKEN, CONF_URL, DEFAULT_CATALOG, DEFAULT_QUEUE, DEFAULT_SYNC_INTERVAL, DOMAIN
from .exceptions import CannotConnect, InvalidAuth, RTAPIError
from .rt_client import RTClient
from .validators import InvalidURL, validate_rt_url

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_QUEUE, default=DEFAULT_QUEUE): str,
        vol.Optional(CONF_HA_URL, default=""): str,
        vol.Optional(CONF_ADDRESS, default=""): str,
        vol.Required(CONF_CATALOG, default=DEFAULT_CATALOG): str,
        vol.Optional(CONF_SYNC_INTERVAL, default=DEFAULT_SYNC_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
    }
)


class HARTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Service Management."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return HARTOptionsFlow()

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


class HARTOptionsFlow(OptionsFlow):
    """Handle options flow for Service Management."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update the config entry data with new options
            new_data = {
                **self.config_entry.data,
                CONF_HA_URL: user_input[CONF_HA_URL],
                CONF_ADDRESS: user_input[CONF_ADDRESS],
                CONF_CATALOG: user_input[CONF_CATALOG],
                CONF_SYNC_INTERVAL: user_input[CONF_SYNC_INTERVAL],
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        current_ha_url = self.config_entry.data.get(CONF_HA_URL, "")
        current_address = self.config_entry.data.get(CONF_ADDRESS, "")
        current_catalog = self.config_entry.data.get(CONF_CATALOG, DEFAULT_CATALOG)
        current_sync_interval = self.config_entry.data.get(CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HA_URL, default=current_ha_url): str,
                    vol.Optional(CONF_ADDRESS, default=current_address): str,
                    vol.Required(CONF_CATALOG, default=current_catalog): str,
                    vol.Optional(CONF_SYNC_INTERVAL, default=current_sync_interval): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
                }
            ),
        )
