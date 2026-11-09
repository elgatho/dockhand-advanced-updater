"""Summary sensors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import DockhandConfigEntry
from .entity import DockhandHubEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DockhandConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    c = entry.runtime_data
    async_add_entities(
        [
            PendingUpdatesSensor(c, "pending_updates"),
            NextRunSensor(c, "next_run"),
            LastRunSensor(c, "last_run"),
        ]
    )


class PendingUpdatesSensor(DockhandHubEntity, SensorEntity):
    @property
    def native_value(self) -> int:
        return sum(1 for i in (self.coordinator.data or {}).values() if i.update_available)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        items = [i for i in (self.coordinator.data or {}).values() if i.update_available]
        return {
            "containers": [f"{i.env_name}/{i.name}" for i in items],
            "excluded": [
                f"{i.env_name}/{i.name}" for i in items if self.coordinator.is_excluded(i.key)
            ],
        }


class NextRunSensor(DockhandHubEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.next_run()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"deferred_date": self.coordinator.state.get("deferred_date")}


class LastRunSensor(DockhandHubEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        raw = self.coordinator.state.get("last_run")
        return dt_util.parse_datetime(raw) if raw else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self.coordinator.state.get("last_result") or {})
