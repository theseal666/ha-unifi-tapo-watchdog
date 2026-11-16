"""Minimal client for a UniFi OS console (UCG, UDM, UDR, UniFi OS Server).

Only what the watchdog needs: log in, list connected clients, list known
clients, and kick a wireless client so it reconnects.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class UniFiError(Exception):
    """Generic UniFi error."""


class UniFiAuthError(UniFiError):
    """Login rejected."""


class UniFiClient:
    """Talks to the Network application through the UniFi OS proxy."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
        site: str = "default",
        verify_ssl: bool = False,
    ) -> None:
        host = host.strip().rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = f"https://{host}"
        self._base = host
        self._session = session
        self._username = username
        self._password = password
        self._site = site
        self._ssl = None if verify_ssl else False
        self._csrf: str | None = None
        self._lock = asyncio.Lock()

    @property
    def _api(self) -> str:
        return f"{self._base}/proxy/network/api/s/{self._site}"

    async def login(self) -> None:
        """Log in and keep the session cookie and CSRF token."""
        try:
            async with self._session.post(
                f"{self._base}/api/auth/login",
                json={
                    "username": self._username,
                    "password": self._password,
                    "rememberMe": False,
                },
                ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (401, 403):
                    raise UniFiAuthError("UniFi rejected the username or password")
                if resp.status != 200:
                    raise UniFiError(f"Login failed with HTTP {resp.status}")
                self._csrf = resp.headers.get("x-csrf-token") or resp.headers.get(
                    "X-Csrf-Token"
                )
        except aiohttp.ClientError as err:
            raise UniFiError(f"Cannot reach UniFi: {err}") from err

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        async with self._lock:
            if self._csrf is None:
                await self.login()
            for attempt in (1, 2):
                headers = {"X-Csrf-Token": self._csrf} if self._csrf else {}
                try:
                    async with self._session.request(
                        method,
                        f"{self._api}/{path}",
                        json=payload,
                        headers=headers,
                        ssl=self._ssl,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        if resp.status == 401 and attempt == 1:
                            await self.login()
                            continue
                        if resp.status != 200:
                            raise UniFiError(f"{path} returned HTTP {resp.status}")
                        if new := resp.headers.get("x-updated-csrf-token"):
                            self._csrf = new
                        body = await resp.json(content_type=None)
                except aiohttp.ClientError as err:
                    raise UniFiError(f"Cannot reach UniFi: {err}") from err
                meta = body.get("meta", {})
                if meta.get("rc") != "ok":
                    raise UniFiError(f"{path}: {meta.get('msg', 'error')}")
                return body.get("data", [])
        raise UniFiError(f"{path}: authentication failed")

    async def connected_clients(self) -> dict[str, dict[str, Any]]:
        """Clients currently connected, keyed by MAC."""
        return {c["mac"].lower(): c for c in await self._request("GET", "stat/sta")}

    async def known_clients(self) -> dict[str, dict[str, Any]]:
        """All clients UniFi remembers (including offline), keyed by MAC."""
        return {c["mac"].lower(): c for c in await self._request("GET", "rest/user")}

    async def kick(self, mac: str) -> None:
        """Disconnect a wireless client so it has to reconnect."""
        await self._request("POST", "cmd/stamgr", {"cmd": "kick-sta", "mac": mac.lower()})
