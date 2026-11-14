
"""Configuration flow for Georgia Natural Gas."""

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    GeorgiaNaturalGasClient,
    GNGAuthenticationError,
    GNGConnectionError,
    GNGError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GeorgiaNaturalGasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a GNG configuration flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial configuration step."""

        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.casefold())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = GeorgiaNaturalGasClient(session, username, password)

            try:
                await client.login()

            except GNGAuthenticationError:
                errors["base"] = "invalid_auth"

            except GNGConnectionError:
                errors["base"] = "cannot_connect"

            except GNGError:
                _LOGGER.exception("GNG configuration validation failed.")
                errors["base"] = "unknown"

            except Exception:
                _LOGGER.exception("Unexpected error during GNG setup.")
                errors["base"] = "unknown"

            else:
                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ):
        """Start reauthentication after an authentication failure."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Validate updated credentials and reload the existing entry."""

        errors = {}
        entry = self._get_reauth_entry()
        username = entry.data[CONF_USERNAME]

        if user_input is not None:
            password = user_input[CONF_PASSWORD]

            session = async_get_clientsession(self.hass)
            client = GeorgiaNaturalGasClient(
                session,
                username,
                password,
            )

            try:
                await client.login()

            except GNGAuthenticationError:
                errors["base"] = "invalid_auth"

            except GNGConnectionError:
                errors["base"] = "cannot_connect"

            except GNGError:
                _LOGGER.exception("GNG reauthentication failed.")
                errors["base"] = "unknown"

            except Exception:
                _LOGGER.exception("Unexpected error during GNG reauthentication.")
                errors["base"] = "unknown"

            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
