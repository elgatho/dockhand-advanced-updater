"""Buttons: manual update for excluded containers + global actions."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DockhandConfigEntry
from .coordinator import ContainerInfo, DockhandCoordinator
from .entity import DockhandContainerEntity, DockhandHubEntity, async_add_dynamic

PARALLEL_UPDATES = 1


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
        await self.coordinator.async_update_container(self._key)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        c = self.container
        return {} if c is None else {"container": c.name, "environment": c.env_name}


class CheckUpdatesButton(DockhandHubEntity, ButtonEntity):
    async def async_press(self) -> None:
        await self.coordinator.async_check_updates()


class RunAutoUpdateButton(DockhandHubEntity, ButtonEntity):
    async def async_press(self) -> None:
        await self.coordinator.async_run_auto_update("manual")
