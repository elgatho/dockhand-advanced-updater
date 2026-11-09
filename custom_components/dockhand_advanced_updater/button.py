"""Buttons: manual update for excluded containers + global actions."""

from __future__ import annotations

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DockhandConfigEntry
from .coordinator import ContainerInfo, DockhandCoordinator
from .entity import DockhandContainerEntity, DockhandHubEntity, async_add_dynamic

PARALLEL_UPDATES = 1

_TEXT = {
    "en": {
        "busy": "An update run is already in progress.",
        "title": "Dockhand",
        "auto_start": "Auto-update started (non-excluded containers only)…",
        "auto_done": "Auto-update finished. Updated: {u}. Failed: {f}.",
        "one_start": "Updating {name}…",
        "one_done": "{name}: update finished.",
        "check_start": "Checking for updates…",
        "check_done": "Update check finished.",
        "none": "none",
    },
    "pl": {
        "busy": "Aktualizacja jest już w toku.",
        "title": "Dockhand",
        "auto_start": "Uruchomiono autoaktualizację (tylko kontenery niewykluczone)…",
        "auto_done": "Autoaktualizacja zakończona. Zaktualizowano: {u}. Błędy: {f}.",
        "one_start": "Aktualizuję {name}…",
        "one_done": "{name}: aktualizacja zakończona.",
        "check_start": "Sprawdzam aktualizacje…",
        "check_done": "Sprawdzanie aktualizacji zakończone.",
        "none": "brak",
    },
}


def _t(hass: HomeAssistant, key: str, **kw: str) -> str:
    lang = "pl" if hass.config.language.startswith("pl") else "en"
    return _TEXT[lang][key].format(**kw)


def _notify(hass: HomeAssistant, entry_id: str, message: str) -> None:
    persistent_notification.async_create(
        hass, message, title=_t(hass, "title"), notification_id=f"dockhand_advanced_updater_{entry_id}"
    )


def _guard(coordinator: DockhandCoordinator) -> None:
    """Refuse a second press while a run is in progress (prevents queued repeats)."""
    if coordinator.busy:
        raise HomeAssistantError(_t(coordinator.hass, "busy"))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DockhandConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    async_add_entities(
        [CheckUpdatesButton(coordinator, "check_updates"), RunAutoUpdateButton(coordinator, "run_auto_update")]
    )

    # Drop buttons of containers that are no longer excluded.
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_update_"
    for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg.domain == "button" and reg.unique_id.startswith(prefix):
            if reg.unique_id[len(prefix):] not in coordinator.excluded:
                registry.async_remove(reg.entity_id)

    def _factory(c: ContainerInfo):
        return UpdateContainerButton(coordinator, c) if coordinator.is_excluded(c.key) else None

    entry.async_on_unload(async_add_dynamic(coordinator, async_add_entities, _factory))


class UpdateContainerButton(DockhandContainerEntity, ButtonEntity):
    _attr_translation_key = "update_container"

    def __init__(self, coordinator: DockhandCoordinator, container: ContainerInfo) -> None:
        super().__init__(coordinator, container, "update")

    async def async_press(self) -> None:
        c = self.coordinator
        _guard(c)
        name = self.container.name if self.container else self._key
        _notify(c.hass, c.config_entry.entry_id, _t(c.hass, "one_start", name=name))
        await c.async_update_container(self._key)
        _notify(c.hass, c.config_entry.entry_id, _t(c.hass, "one_done", name=name))

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        c = self.container
        return {} if c is None else {"container": c.name, "environment": c.env_name}


class CheckUpdatesButton(DockhandHubEntity, ButtonEntity):
    async def async_press(self) -> None:
        c = self.coordinator
        _guard(c)
        _notify(c.hass, c.config_entry.entry_id, _t(c.hass, "check_start"))
        await c.async_check_updates()
        _notify(c.hass, c.config_entry.entry_id, _t(c.hass, "check_done"))


class RunAutoUpdateButton(DockhandHubEntity, ButtonEntity):
    async def async_press(self) -> None:
        c = self.coordinator
        _guard(c)
        _notify(c.hass, c.config_entry.entry_id, _t(c.hass, "auto_start"))
        result = await c.async_run_auto_update("manual")
        none = _t(c.hass, "none")
        _notify(
            c.hass,
            c.config_entry.entry_id,
            _t(
                c.hass,
                "auto_done",
                u=", ".join(result["updated"]) or none,
                f="; ".join(result["failed"]) or none,
            ),
        )
