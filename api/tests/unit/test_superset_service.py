"""SupersetService unit test — httpx MockTransport, no real Superset. Verifies
the login -> guest-token flow and that every token is RLS-scoped to the
requesting user (CLAUDE.md per-user guest-token rule)."""

import json

import httpx

from src.services.superset_service import SupersetService


async def test_guest_token_is_rls_scoped_to_user():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/security/login"):
            return httpx.Response(200, json={"access_token": "admin-tok"})
        if request.url.path.endswith("/security/guest_token/"):
            captured["body"] = json.loads(request.content)
            captured["auth"] = request.headers.get("authorization")
            return httpx.Response(200, json={"token": "guest-tok"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        svc = SupersetService(
            http,
            base_url="http://superset:8088",
            admin_user="admin",
            admin_password="pw",
            guest_username="embed-guest",
        )
        token = await svc.mint_guest_token(42, "dash-1")

    assert token == "guest-tok"
    assert captured["auth"] == "Bearer admin-tok"
    assert captured["body"]["rls"] == [{"clause": "user_id = 42"}]
    assert captured["body"]["resources"] == [{"type": "dashboard", "id": "dash-1"}]
