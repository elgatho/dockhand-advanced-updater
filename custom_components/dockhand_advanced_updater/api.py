"""Minimal async client for the Dockhand REST API."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import TIMEOUT_CHECK, TIMEOUT_DEFAULT, TIMEOUT_UPDATE


class DockhandError(Exception):
    """Generic Dockhand API error."""


class DockhandConnectionError(DockhandError):
    """Dockhand could not be reached."""


class DockhandAuthError(DockhandError):
    """Dockhand rejected the credentials (HTTP 401)."""


class DockhandClient:
    """Talks to Dockhand using a user-scoped API token (Bearer)."""

    def __init__(
        self, session: aiohttp.ClientSession, url: str, token: str | None
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._token = token

    @property
    def url(self) -> str:
        return self._url

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        timeout: int = TIMEOUT_DEFAULT,
        parse: bool = True,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with self._session.request(
                method,
                f"{self._url}{path}",
                params=params,
                json=json,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 401:
                    raise DockhandAuthError("Authentication required or token invalid")
                if resp.status >= 400:
                    text = (await resp.text())[:200]
                    raise DockhandError(f"HTTP {resp.status} on {path}: {text}")
                if not parse:
                    await resp.read()
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise DockhandConnectionError(
                f"Cannot reach Dockhand at {self._url}: {err}"
            ) from err
        except ValueError as err:  # invalid JSON
            raise DockhandError(f"Invalid response on {path}: {err}") from err

    async def get_environments(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/environments")
        if not isinstance(data, list):
            raise DockhandError("Unexpected response from /api/environments")
        return data

    async def get_containers(self, env_id: int) -> list[dict[str, Any]]:
        data = await self._request(
            "GET", "/api/containers", params={"env": env_id, "all": "true"}
        )
        return data if isinstance(data, list) else []

    async def get_pending_updates(self, env_id: int) -> list[dict[str, Any]]:
        data = await self._request(
            "GET", "/api/containers/pending-updates", params={"env": env_id}
        )
        if isinstance(data, dict):
            return data.get("pendingUpdates") or []
        return []

    async def check_updates(self, env_id: int) -> None:
        """Ask Dockhand to run a fresh image-update check (result is discarded)."""
        await self._request(
            "POST",
            "/api/containers/check-updates",
            params={"env": env_id},
            timeout=TIMEOUT_CHECK,
            parse=False,
        )

    async def update_containers(
        self, env_id: int, container_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Recreate containers with their latest images; returns per-container results."""
        data = await self._request(
            "POST",
            "/api/containers/batch-update",
            params={"env": env_id},
            json={"containerIds": container_ids},
            timeout=TIMEOUT_UPDATE,
        )
        return (data or {}).get("results") or []
