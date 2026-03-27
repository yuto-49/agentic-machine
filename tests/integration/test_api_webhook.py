"""Integration tests for POST /api/webhook/oclaw."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.integration

VALID_BODY = {
    "sender_id": "U_TEST",
    "sender_name": "TestUser",
    "platform": "slack",
    "channel": "claudius",
    "text": "Hello Claudius!",
}


class TestOpenClawWebhook:
    async def test_valid_request(self, client):
        from config_app import settings
        with (
            patch("api.webhook.agent_step", new_callable=AsyncMock, return_value="Hello!") as mock_step,
            patch("api.webhook.httpx.AsyncClient") as mock_http,
        ):
            mock_http.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
            resp = await client.post(
                "/api/webhook/oclaw",
                json=VALID_BODY,
                headers={"X-Webhook-Secret": settings.webhook_secret},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["response"] == "Hello!"
            mock_step.assert_awaited_once()

    async def test_invalid_secret(self, client):
        resp = await client.post(
            "/api/webhook/oclaw",
            json=VALID_BODY,
            headers={"X-Webhook-Secret": "definitely-wrong-secret-value"},
        )
        assert resp.status_code == 401

    async def test_missing_secret_header(self, client):
        # When the header is entirely absent, request.headers.get returns None
        # which != settings.webhook_secret (even if it's "")
        from config_app import settings
        if settings.webhook_secret == "":
            # If secret is empty, missing header (None) != "" → 401
            resp = await client.post("/api/webhook/oclaw", json=VALID_BODY)
            assert resp.status_code == 401
        else:
            resp = await client.post("/api/webhook/oclaw", json=VALID_BODY)
            assert resp.status_code == 401


class TestAdminTrigger:
    async def test_daily_morning(self, client):
        with patch("api.webhook.agent_step", new_callable=AsyncMock, return_value="Morning check done."):
            resp = await client.post("/api/admin/agent/trigger", json={
                "type": "daily_morning",
            })
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    async def test_low_stock(self, client):
        with patch("api.webhook.agent_step", new_callable=AsyncMock, return_value="Stock OK."):
            resp = await client.post("/api/admin/agent/trigger", json={
                "type": "low_stock_check",
            })
            assert resp.status_code == 200

    async def test_nightly(self, client):
        with patch("api.webhook.agent_step", new_callable=AsyncMock, return_value="Night done."):
            resp = await client.post("/api/admin/agent/trigger", json={
                "type": "nightly_reconciliation",
            })
            assert resp.status_code == 200

    async def test_manual(self, client):
        with patch("api.webhook.agent_step", new_callable=AsyncMock, return_value="Manual done."):
            resp = await client.post("/api/admin/agent/trigger", json={
                "type": "manual",
                "message": "Check something",
            })
            assert resp.status_code == 200
