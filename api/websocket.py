"""WebSocket endpoint for real-time iPad updates (stock changes, price updates)."""

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

# Connected WebSocket clients (iPad instances)
_connected_clients: list[WebSocket] = []


async def broadcast(message: dict[str, Any]) -> None:
    """Send a message to all connected WebSocket clients."""
    disconnected = []
    for ws in _connected_clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _connected_clients.remove(ws)


@router.websocket("/ws/updates")
async def websocket_updates(websocket: WebSocket):
    """WebSocket endpoint for iPad real-time updates.

    Messages sent to clients:
    - {"type": "stock_update", "product_id": int, "quantity": int}
    - {"type": "price_update", "product_id": int, "sell_price": float}
    - {"type": "status", "online": bool}
    """
    await websocket.accept()
    _connected_clients.append(websocket)
    logger.info("WebSocket client connected (total: %d)", len(_connected_clients))

    try:
        # Keep connection alive — listen for pings or close
        while True:
            data = await websocket.receive_text()
            # Clients can send "ping" to keep alive
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        _connected_clients.remove(websocket)
        logger.info("WebSocket client disconnected (total: %d)", len(_connected_clients))
