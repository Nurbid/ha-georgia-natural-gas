"""Configuration and options flows for Georgia Natural Gas."""

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlowWithReload
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .api import (
    GeorgiaNaturalGasClient,
    GNGAuthenticationError,
    GNGConnectionError,
    GNGError,
)
from .const import (
    ACCOUNT_OPTIONS,
    CONF_ACCOUNT_SELECTION,
    DEFAULT_ACCOUNT_SELECTION,
    DOMAIN,
)

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
                    title="Georgia Natural Gas",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                    options={CONF_ACCOUNT_SELECTION: DEFAULT_ACCOUNT_SELECTION},
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

    async def async_step_reconfigure(self, user_input=None):
        """Allow the user to update GNG credentials."""

        errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            if username.casefold() != entry.unique_id:
                await self.async_set_unique_id(username.casefold())
                self._abort_if_unique_id_configured()

            client = GeorgiaNaturalGasClient(
                async_get_clientsession(self.hass),
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
                _LOGGER.exception("GNG reconfiguration validation failed.")
                errors["base"] = "unknown"

            except Exception:
                _LOGGER.exception("Unexpected error during GNG reconfiguration.")
                errors["base"] = "unknown"

            else:
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=username.casefold(),
                    data_updates={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=entry.data[CONF_USERNAME],
                    ): str,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithReload:
        """Return the account-selection options flow."""

        return GeorgiaNaturalGasOptionsFlow()


class GeorgiaNaturalGasOptionsFlow(OptionsFlowWithReload):
    """Manage the selected GNG account."""

    async def async_step_init(self, user_input=None):
        """Allow the user to select the account used for billing data."""

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_SELECTION): SelectSelector(
                    SelectSelectorConfig(options=ACCOUNT_OPTIONS)
                )
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_ACCOUNT_SELECTION: self.config_entry.options.get(
                        CONF_ACCOUNT_SELECTION,
                        DEFAULT_ACCOUNT_SELECTION,
                    )
                },
            ),
        )
