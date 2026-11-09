"""Config flow and options flow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DockhandConfigEntry
from .api import DockhandAuthError, DockhandClient, DockhandError
from .const import (
    CONF_CHECK_BEFORE,
    CONF_ENVIRONMENTS,
    CONF_EXCLUDED,
    CONF_ONLY_HOME,
    CONF_PERSONS,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_UPDATE_DAYS,
    CONF_UPDATE_TIME,
    CONF_URL,
    CONF_VERIFY_SSL,
    DAYS,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from .coordinator import DockhandCoordinator


def _normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


async def _validate(hass, data: Mapping[str, Any]) -> tuple[str, dict[str, str]]:
    """Return (normalized_url, errors)."""
    url = _normalize_url(data[CONF_URL])
    client = DockhandClient(
        async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, True)),
        url,
        data.get(CONF_TOKEN) or None,
    )
    try:
        await client.get_environments()
    except DockhandAuthError:
        return url, {"base": "invalid_auth"}
    except DockhandError:
        return url, {"base": "cannot_connect"}
    except Exception:  # noqa: BLE001
        return url, {"base": "unknown"}
    return url, {}


def _user_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=d.get(CONF_URL, "http://")): str,
            vol.Optional(CONF_TOKEN, default=d.get(CONF_TOKEN, "")): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_VERIFY_SSL, default=d.get(CONF_VERIFY_SSL, True)): bool,
        }
    )


class DockhandConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url, errors = await _validate(self.hass, user_input)
            if not errors:
                await self.async_set_unique_id(url.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Dockhand ({url.split('://', 1)[1]})",
                    data={
                        CONF_URL: url,
                        CONF_TOKEN: user_input.get(CONF_TOKEN) or None,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                    options=dict(DEFAULT_OPTIONS),
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_user_schema(), user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_TOKEN: user_input[CONF_TOKEN]}
            _, errors = await _validate(self.hass, data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: DockhandConfigEntry) -> OptionsFlow:
        return DockhandOptionsFlow()


class DockhandOptionsFlow(OptionsFlow):
    """Step 1: schedule & environments. Step 2: choose excluded containers."""

    def __init__(self) -> None:
        self._opts: dict[str, Any] = {}

    @property
    def _coordinator(self) -> DockhandCoordinator | None:
        entry = self.config_entry
        return getattr(entry, "runtime_data", None)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = {**DEFAULT_OPTIONS, **self.config_entry.options}

        if user_input is not None:
            # cleared optional multi-selects are omitted by the frontend
            user_input.setdefault(CONF_ENVIRONMENTS, [])
            user_input.setdefault(CONF_PERSONS, [])
            if not user_input.get(CONF_UPDATE_DAYS):
                errors["base"] = "days_required"
            elif user_input.get(CONF_ONLY_HOME) and not user_input.get(CONF_PERSONS):
                errors["base"] = "persons_required"
            else:
                self._opts = {**current, **user_input}
                return await self.async_step_containers()
            current = {**current, **user_input}

        env_options: list[selector.SelectOptionDict] = []
        if (coord := self._coordinator) is not None:
            env_options = [
                selector.SelectOptionDict(value=str(i), label=n)
                for i, n in sorted(coord.environments.items())
            ]
        # keep previously selected envs visible even if they are currently offline
        known = {o["value"] for o in env_options}
        for e in current[CONF_ENVIRONMENTS]:
            if str(e) not in known:
                env_options.append(selector.SelectOptionDict(value=str(e), label=f"#{e}"))

        schema = vol.Schema(
            {
                vol.Optional(CONF_ENVIRONMENTS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=env_options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_UPDATE_TIME): selector.TimeSelector(),
                vol.Required(CONF_UPDATE_DAYS): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=DAYS,
                        multiple=True,
                        translation_key="weekdays",
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_ONLY_HOME): selector.BooleanSelector(),
                vol.Optional(CONF_PERSONS): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="person", multiple=True)
                ),
                vol.Required(CONF_CHECK_BEFORE): selector.BooleanSelector(),
                vol.Required(CONF_SCAN_INTERVAL): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=1440,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
            }
        )
        suggested = {
            **current,
            CONF_ENVIRONMENTS: [str(e) for e in current[CONF_ENVIRONMENTS]],
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )

    async def async_step_containers(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coord = self._coordinator
        selected_envs = {str(e) for e in self._opts[CONF_ENVIRONMENTS]}
        labels: dict[str, str] = {}
        if coord is not None:
            for key, info in (coord.data or {}).items():
                if selected_envs and str(info.env_id) not in selected_envs:
                    continue
                labels[key] = f"{info.env_name} / {info.name}"
        # keep exclusions of containers that are currently unknown (e.g. env offline)
        for key in self._opts[CONF_EXCLUDED]:
            labels.setdefault(key, f"{key.split(':', 1)[-1]} ({key.split(':', 1)[0]}) ⚠")

        if user_input is not None:
            # exclusions outside the visible list are preserved only if still listed
            chosen = list(user_input.get(CONF_EXCLUDED, []))
            self._opts[CONF_EXCLUDED] = chosen
            self._opts[CONF_ENVIRONMENTS] = [int(e) for e in self._opts[CONF_ENVIRONMENTS]]
            self._opts[CONF_SCAN_INTERVAL] = int(self._opts[CONF_SCAN_INTERVAL])
            return self.async_create_entry(data=self._opts)

        options = [
            selector.SelectOptionDict(value=k, label=v)
            for k, v in sorted(labels.items(), key=lambda kv: kv[1].lower())
        ]
        schema = vol.Schema(
            {
                vol.Optional(CONF_EXCLUDED): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="containers",
            data_schema=self.add_suggested_values_to_schema(
                schema, {CONF_EXCLUDED: list(self._opts[CONF_EXCLUDED])}
            ),
        )
