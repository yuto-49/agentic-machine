"""Integration tests for WebSocket /ws/updates."""

import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture
def sync_app(test_app):
    """Wrap the async test_app fixture for sync TestClient usage."""
    return test_app


class TestWebSocket:
    def test_connect_and_ping_pong(self, sync_app):
        """Sync test using Starlette TestClient for WebSocket."""
        with TestClient(sync_app) as tc:
            with tc.websocket_connect("/ws/updates") as ws:
                ws.send_text("ping")
                data = ws.receive_json()
                assert data["type"] == "pong"

    def test_disconnect(self, sync_app):
        with TestClient(sync_app) as tc:
            with tc.websocket_connect("/ws/updates") as ws:
                ws.send_text("ping")
                ws.receive_json()
            # Disconnected — no error
