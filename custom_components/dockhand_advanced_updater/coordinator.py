"""Data coordinator, scheduler and update logic."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DockhandAuthError, DockhandClient, DockhandError
from .const import (
    CONF_CHECK_BEFORE,
    CONF_ENVIRONMENTS,
    CONF_EXCLUDED,
    CONF_ONLY_HOME,
    CONF_PERSONS,
    CONF_SCAN_INTERVAL,
    CONF_UPDATE_DAYS,
    CONF_UPDATE_TIME,
    DAYS,
    DEFAULT_OPTIONS,
    DOMAIN,
    EVENT_RUN_FINISHED,
    LOGGER,
    container_key,
)

if TYPE_CHECKING:
    pass

STORAGE_VERSION = 1


@dataclass
class ContainerInfo:
    """A container as seen by Dockhand."""

    key: str
    env_id: int
    env_name: str
    id: str
    name: str
    image: str
    state: str
    status: str
    update_available: bool = False
    pinned: bool = False
    release_wait_hours: int = 0
    checked_at: str | None = None


class DockhandCoordinator(DataUpdateCoordinator[dict[str, ContainerInfo]]):
    """Polls Dockhand and runs the scheduled auto-update."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: DockhandClient
    ) -> None:
        opts = self.options_of(entry)
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=max(1, int(opts[CONF_SCAN_INTERVAL]))),
        )
        self.client = client
        self.environments: dict[int, str] = {}
        self.env_online: dict[int, bool] = {}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.state: dict[str, Any] = {
            "enabled": True,
            "last_run": None,
            "last_result": None,
            "deferred_date": None,
        }
        self._lock = asyncio.Lock()
        self._unsubs: list[CALLBACK_TYPE] = []

    # ------------------------------------------------------------------ options
    @staticmethod
    def options_of(entry: ConfigEntry) -> dict[str, Any]:
        return {**DEFAULT_OPTIONS, **entry.options}

    @property
    def busy(self) -> bool:
        """True while an update run holds the lock."""
        return self._lock.locked()

    @property
    def options(self) -> dict[str, Any]:
        return self.options_of(self.config_entry)

    @property
    def excluded(self) -> set[str]:
        return set(self.options[CONF_EXCLUDED])

    @property
    def enabled(self) -> bool:
        return bool(self.state["enabled"])

    def is_excluded(self, key: str) -> bool:
        return key in self.excluded

    # ---------------------------------------------------------------- lifecycle
    async def async_load(self) -> None:
        if (stored := await self._store.async_load()) is not None:
            self.state.update(stored)

    async def _async_save(self) -> None:
        await self._store.async_save(self.state)

    async def async_remove_storage(self) -> None:
        await self._store.async_remove()

    @callback
    def async_start(self) -> None:
        """Register the schedule and presence listeners."""
        opts = self.options
        t = dt_util.parse_time(opts[CONF_UPDATE_TIME]) or dt_util.parse_time("03:00:00")
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._scheduled_tick, hour=t.hour, minute=t.minute, second=0
            )
        )
        if opts[CONF_ONLY_HOME] and opts[CONF_PERSONS]:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, list(opts[CONF_PERSONS]), self._person_changed
                )
            )

    @callback
    def async_stop(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()

    # -------------------------------------------------------------------- poll
    async def _async_update_data(self) -> dict[str, ContainerInfo]:
        try:
            envs = await self.client.get_environments()
        except DockhandAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except DockhandError as err:
            raise UpdateFailed(str(err)) from err

        selected = {int(e) for e in self.options[CONF_ENVIRONMENTS]}
        result: dict[str, ContainerInfo] = {}
        environments: dict[int, str] = {}
        failures = 0

        for env in envs:
            env_id = int(env["id"])
            if selected and env_id not in selected:
                continue
            env_name = str(env.get("name", env_id))
            environments[env_id] = env_name
            try:
                containers = await self.client.get_containers(env_id)
                pending = {
                    p["containerName"]: p
                    for p in await self.client.get_pending_updates(env_id)
                    if p.get("containerName")
                }
            except DockhandAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except DockhandError as err:
                failures += 1
                LOGGER.warning("Environment %s unavailable: %s", env_name, err)
                self.env_online[env_id] = False
                # keep last known data so exclusions / entities stay consistent
                for key, info in (self.data or {}).items():
                    if info.env_id == env_id:
                        result[key] = info
                continue

            self.env_online[env_id] = True
            for c in containers:
                name = str(c.get("name", "")).lstrip("/")
                if not name:
                    continue
                p = pending.get(name)
                key = container_key(env_id, name)
                result[key] = ContainerInfo(
                    key=key,
                    env_id=env_id,
                    env_name=env_name,
                    id=str(c.get("id", "")),
                    name=name,
                    image=str(c.get("image", "")),
                    state=str(c.get("state", "")),
                    status=str(c.get("status", "")),
                    update_available=bool(p and p.get("hasImageUpdate")),
                    pinned=bool(p and p.get("pinnedToDigest")),
                    release_wait_hours=int((p or {}).get("releaseAgeRemainingHours") or 0),
                    checked_at=(p or {}).get("checkedAt"),
                )

        if environments and failures == len(environments):
            raise UpdateFailed("No Dockhand environment is reachable")
        self.environments = environments
        return result

    # ---------------------------------------------------------------- schedule
    def anyone_home(self) -> bool:
        for entity_id in self.options[CONF_PERSONS]:
            if (st := self.hass.states.get(entity_id)) and st.state == "home":
                return True
        return False

    def next_run(self) -> datetime | None:
        days = {DAYS.index(d) for d in self.options[CONF_UPDATE_DAYS] if d in DAYS}
        t = dt_util.parse_time(self.options[CONF_UPDATE_TIME])
        if not self.enabled or not days or t is None:
            return None
        now = dt_util.now()
        for offset in range(8):
            cand = datetime.combine(
                now.date() + timedelta(days=offset), t, tzinfo=now.tzinfo
            )
            if cand > now and cand.weekday() in days:
                return cand
        return None

    @callback
    def _scheduled_tick(self, now: datetime) -> None:
        self.hass.async_create_task(self._async_handle_schedule(now))

    async def _async_handle_schedule(self, now: datetime) -> None:
        local = dt_util.as_local(now)
        days = {DAYS.index(d) for d in self.options[CONF_UPDATE_DAYS] if d in DAYS}
        if not self.enabled or local.weekday() not in days:
            return
        if self.options[CONF_ONLY_HOME] and not self.anyone_home():
            LOGGER.info("Nobody is home; auto-update deferred until someone arrives")
            self.state["deferred_date"] = local.date().isoformat()
            await self._async_save()
            self.async_update_listeners()
            return
        self.state["deferred_date"] = None
        await self.async_run_auto_update("schedule")

    async def _person_changed(self, event: Event[EventStateChangedData]) -> None:
        new = event.data["new_state"]
        if new is None or new.state != "home":
            return
        today = dt_util.now().date().isoformat()
        if not self.enabled or self.state.get("deferred_date") != today:
            return
        LOGGER.info("%s arrived home; running deferred auto-update", new.entity_id)
        self.state["deferred_date"] = None
        await self.async_run_auto_update("arrival")

    # ------------------------------------------------------------------ actions
    def auto_candidates(self) -> list[ContainerInfo]:
        excluded = self.excluded
        return [
            c
            for c in (self.data or {}).values()
            if c.update_available
            and c.key not in excluded
            and c.release_wait_hours <= 0
            and self.env_online.get(c.env_id)
        ]

    async def async_check_updates(self) -> None:
        """Trigger a fresh image check in every monitored environment."""
        async with self._lock:
            await self._async_check_all()
        await self.async_refresh()

    async def _async_check_all(self) -> None:
        for env_id, env_name in self.environments.items():
            try:
                await self.client.check_updates(env_id)
            except DockhandError as err:
                LOGGER.warning("Update check failed for %s: %s", env_name, err)

    async def async_run_auto_update(self, reason: str = "manual") -> dict[str, Any]:
        """Update every non-excluded container that has a pending update."""
        async with self._lock:
            if self.options[CONF_CHECK_BEFORE] or reason == "schedule":
                await self._async_check_all()
            await self.async_refresh()
            result = await self._async_update(self.auto_candidates(), reason)
        await self.async_refresh()
        return result

    async def async_update_container(self, key: str) -> None:
        """Manually update one container (used by the per-container button)."""
        async with self._lock:
            info = (self.data or {}).get(key)
            if info is None:
                raise HomeAssistantError(f"Container {key} no longer exists")
            result = await self._async_update([info], "manual_container")
        await self.async_refresh()
        if result["failed"]:
            raise HomeAssistantError("; ".join(result["failed"]))

    async def _async_update(
        self, containers: list[ContainerInfo], reason: str
    ) -> dict[str, Any]:
        updated: list[str] = []
        failed: list[str] = []
        by_env: dict[int, list[ContainerInfo]] = {}
        for c in containers:
            by_env.setdefault(c.env_id, []).append(c)

        for env_id, items in by_env.items():
            try:
                results = await self.client.update_containers(
                    env_id, [c.id for c in items]
                )
            except DockhandAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except DockhandError as err:
                failed.extend(f"{c.env_name}/{c.name}: {err}" for c in items)
                continue
            seen: set[str] = set()
            for r in results:
                label = f"{items[0].env_name}/{r.get('containerName', '?')}"
                seen.add(str(r.get("containerName")))
                if r.get("success"):
                    updated.append(label)
                else:
                    failed.append(f"{label}: {r.get('error', 'unknown error')}")
            failed.extend(
                f"{c.env_name}/{c.name}: no result returned"
                for c in items
                if c.name not in seen
            )

        result = {
            "reason": reason,
            "updated": updated,
            "failed": failed,
            "finished": dt_util.utcnow().isoformat(),
        }
        self.state["last_run"] = result["finished"]
        self.state["last_result"] = result
        await self._async_save()
        self.hass.bus.async_fire(EVENT_RUN_FINISHED, result)
        LOGGER.info("Update run (%s): %d updated, %d failed", reason, len(updated), len(failed))
        return result

    async def async_set_enabled(self, enabled: bool) -> None:
        self.state["enabled"] = enabled
        await self._async_save()
        self.async_update_listeners()
