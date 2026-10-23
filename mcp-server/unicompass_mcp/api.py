"""Async client for the UniCompass FastAPI backend, acting as one user.

Authentication: either a ready JWT (UNICOMPASS_TOKEN) or credentials
(UNICOMPASS_EMAIL / UNICOMPASS_PASSWORD). Backend tokens expire after 24 h,
so with credentials the client logs in lazily and once more on a 401.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_API_URL = "http://localhost:8000"


class APIError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


@dataclass
class Credentials:
    token: str | None = None
    email: str | None = None
    password: str | None = None

    @classmethod
    def from_env(cls) -> "Credentials":
        return cls(
            token=os.environ.get("UNICOMPASS_TOKEN") or None,
            email=os.environ.get("UNICOMPASS_EMAIL") or None,
            password=os.environ.get("UNICOMPASS_PASSWORD") or None,
        )

    @property
    def can_login(self) -> bool:
        return bool(self.email and self.password)


class UniCompassAPI:
    def __init__(
        self,
        base_url: str = DEFAULT_API_URL,
        credentials: Credentials | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._creds = credentials or Credentials()
        self._token = self._creds.token
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), transport=transport, timeout=timeout
        )

    @classmethod
    def from_env(cls) -> "UniCompassAPI":
        return cls(
            os.environ.get("UNICOMPASS_API_URL", DEFAULT_API_URL),
            Credentials.from_env(),
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    # ── Transport ────────────────────────────────────────────────────

    async def _login(self) -> None:
        resp = await self._http.post(
            "/auth/login",
            json={"email": self._creds.email, "password": self._creds.password},
        )
        if resp.status_code != 200:
            raise APIError(resp.status_code, _detail(resp) or "login failed")
        self._token = resp.json()["access_token"]

    async def _request(self, method: str, path: str, *, auth: bool = True, **kwargs) -> Any:
        if auth and self._token is None:
            if not self._creds.can_login:
                raise APIError(
                    401,
                    "not signed in: set UNICOMPASS_EMAIL and UNICOMPASS_PASSWORD "
                    "(or UNICOMPASS_TOKEN) in the MCP server's environment",
                )
            await self._login()

        for attempt in range(2):
            headers = {"Authorization": f"Bearer {self._token}"} if auth else {}
            resp = await self._http.request(method, path, headers=headers, **kwargs)
            if resp.status_code == 401 and auth and attempt == 0 and self._creds.can_login:
                await self._login()  # token expired — refresh once
                continue
            break

        if resp.status_code >= 400:
            raise APIError(resp.status_code, _detail(resp))
        return resp.json()

    # ── Endpoints ────────────────────────────────────────────────────

    async def feed(
        self,
        *,
        skills: list[str] | None = None,
        category: str | None = None,
        limit: int = 10,
        offset: int = 0,
        active_only: bool = True,
    ) -> dict:
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "active_only": str(active_only).lower(),
        }
        if category:
            params["category"] = category
        if skills:
            params["skills"] = ",".join(skills)
        return await self._request("GET", "/api/feeds/rss", auth=False, params=params)

    async def item(self, item_id: int) -> dict:
        return await self._request("GET", f"/api/feeds/items/{item_id}", auth=False)

    async def profile(self) -> dict:
        return await self._request("GET", "/profile/me")

    async def update_profile(
        self, *, skills: list[str] | None = None, interests: list[str] | None = None
    ) -> dict:
        body = {k: v for k, v in {"skills": skills, "interests": interests}.items() if v is not None}
        return await self._request("PATCH", "/profile/me", json=body)

    async def bookmarks(self, *, category: str | None = None, limit: int = 200) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if category:
            params["category"] = category
        return await self._request("GET", "/api/bookmarks", params=params)

    async def bookmark_ids(self) -> set[int]:
        return set((await self._request("GET", "/api/bookmarks/ids"))["ids"])

    async def toggle_bookmark(self, item_id: int) -> dict:
        return await self._request("POST", f"/api/bookmarks/{item_id}")

    async def remove_bookmark(self, item_id: int) -> dict:
        return await self._request("DELETE", f"/api/bookmarks/{item_id}")


def _detail(resp: httpx.Response) -> str:
    try:
        detail = resp.json().get("detail")
    except Exception:
        detail = None
    if isinstance(detail, list):  # FastAPI validation errors
        detail = "; ".join(str(d.get("msg", d)) for d in detail)
    return str(detail or resp.reason_phrase or "request failed")
