"""Talks to the Superset REST API. Mints per-user guest tokens for embedded
dashboards, scoping every token with a Row-Level-Security rule on user_id so a
user can only ever see their own data (CLAUDE.md security rule)."""

import httpx
import structlog

from ..core.exceptions import SupersetError

log = structlog.get_logger()


class SupersetService:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str,
        admin_user: str,
        admin_password: str,
        guest_username: str,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._admin_user = admin_user
        self._admin_password = admin_password
        self._guest_username = guest_username

    async def _login(self) -> str:
        """Authenticate as admin and return an access token."""
        try:
            resp = await self._http.post(
                f"{self._base_url}/api/v1/security/login",
                json={
                    "username": self._admin_user,
                    "password": self._admin_password,
                    "provider": "db",
                    "refresh": True,
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise SupersetError(f"Superset login failed: {exc}") from exc
        return resp.json()["access_token"]

    async def mint_guest_token(self, user_id: int, dashboard_id: str) -> str:
        """Mint a guest token scoped to one dashboard and RLS-filtered to this
        user's rows only."""
        access_token = await self._login()
        try:
            resp = await self._http.post(
                f"{self._base_url}/api/v1/security/guest_token/",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "user": {"username": self._guest_username},
                    "resources": [{"type": "dashboard", "id": dashboard_id}],
                    "rls": [{"clause": f"user_id = {int(user_id)}"}],
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise SupersetError(f"Superset guest-token mint failed: {exc}") from exc
        token = resp.json()["token"]
        log.info("guest_token_minted", user_id=user_id, dashboard_id=dashboard_id)
        return token
