"""Per-container "update available" binary sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DockhandConfigEntry
from .coordinator import ContainerInfo, DockhandCoordinator
from .entity import DockhandContainerEntity, async_add_dynamic

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DockhandConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entry.async_on_unload(
        async_add_dynamic(
            coordinator,
            async_add_entities,
            lambda c: UpdateAvailableSensor(coordinator, c),
        )
    )


class UpdateAvailableSensor(DockhandContainerEntity, BinarySensorEntity):
    _attr_translation_key = "update_available"

    def __init__(self, coordinator: DockhandCoordinator, container: ContainerInfo) -> None:
        super().__init__(coordinator, container, "update_available")

    @property
    def is_on(self) -> bool | None:
        c = self.container
        return None if c is None else c.update_available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.container
        if c is None:
            return {}
        return {
            "container": c.name,
            "environment": c.env_name,
            "image": c.image,
            "container_state": c.state,
            "excluded_from_auto_update": self.coordinator.is_excluded(c.key),
            "pinned_to_digest": c.pinned,
            "release_wait_hours": c.release_wait_hours,
            "checked_at": c.checked_at,
        }
