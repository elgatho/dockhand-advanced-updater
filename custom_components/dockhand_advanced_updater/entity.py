"""Base entities and helpers."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ContainerInfo, DockhandCoordinator


def hub_device(coordinator: DockhandCoordinator) -> DeviceInfo:
    entry = coordinator.config_entry
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Dockhand",
        manufacturer="Dockhand",
        configuration_url=coordinator.client.url,
    )


class DockhandHubEntity(CoordinatorEntity[DockhandCoordinator]):
    """Entity attached to the Dockhand hub device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DockhandCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = hub_device(coordinator)


class DockhandContainerEntity(CoordinatorEntity[DockhandCoordinator]):
    """Entity bound to one container, grouped under its environment device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DockhandCoordinator, container: ContainerInfo, prefix: str
    ) -> None:
        super().__init__(coordinator)
        self._key = container.key
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{prefix}_{container.key}"
        self._attr_translation_placeholders = {"container": container.name}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_env_{container.env_id}")},
            name=f"Dockhand – {container.env_name}",
            manufacturer="Dockhand",
            via_device=(DOMAIN, entry_id),
        )

    @property
    def container(self) -> ContainerInfo | None:
        return (self.coordinator.data or {}).get(self._key)

    @property
    def available(self) -> bool:
        c = self.container
        return (
            super().available
            and c is not None
            and self.coordinator.env_online.get(c.env_id, False)
        )


def async_add_dynamic(
    coordinator: DockhandCoordinator,
    add_entities: Callable[[list[Entity]], None],
    factory: Callable[[ContainerInfo], Entity | None],
) -> Callable[[], None]:
    """Create entities for containers as they appear; returns the listener remover."""
    known: set[str] = set()

    def _sync() -> None:
        new: list[Entity] = []
        for key, info in (coordinator.data or {}).items():
            if key in known:
                continue
            if (entity := factory(info)) is not None:
                known.add(key)
                new.append(entity)
        if new:
            add_entities(new)

    _sync()
    return coordinator.async_add_listener(_sync)
