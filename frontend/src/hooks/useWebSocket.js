import { useEffect, useState } from "react";

const RECONNECT_MS = 3000;
const CLOSE_GRACE_MS = 1000;
const sharedSockets = new Map();

function notifySubscribers(shared) {
  const snapshot = {
    lastMessage: shared.lastMessage,
    isConnected: shared.isConnected,
  };
  shared.subscribers.forEach((callback) => callback(snapshot));
}

function connectSharedSocket(shared) {
  const ws = new WebSocket(shared.wsUrl);
  shared.ws = ws;

  ws.onopen = () => {
    if (shared.ws !== ws) return;
    shared.isConnected = true;
    notifySubscribers(shared);
  };

  ws.onmessage = (event) => {
    if (shared.ws !== ws) return;
    try {
      shared.lastMessage = JSON.parse(event.data);
      notifySubscribers(shared);
    } catch {
      // Ignore non-JSON messages
    }
  };

  ws.onclose = () => {
    if (shared.ws !== ws) return;
    shared.ws = null;
    shared.isConnected = false;
    notifySubscribers(shared);

    if (shared.refCount > 0) {
      clearTimeout(shared.reconnectTimer);
      shared.reconnectTimer = setTimeout(() => {
        shared.reconnectTimer = null;
        connectSharedSocket(shared);
      }, RECONNECT_MS);
    }
  };

  ws.onerror = () => {
    ws.close();
  };
}

function getSharedSocket(wsUrl) {
  let shared = sharedSockets.get(wsUrl);
  if (shared) return shared;

  shared = {
    wsUrl,
    ws: null,
    isConnected: false,
    lastMessage: null,
    subscribers: new Set(),
    refCount: 0,
    reconnectTimer: null,
    closeTimer: null,
  };

  sharedSockets.set(wsUrl, shared);
  return shared;
}

function subscribeSharedSocket(wsUrl, callback) {
  const shared = getSharedSocket(wsUrl);

  clearTimeout(shared.closeTimer);
  shared.closeTimer = null;

  shared.refCount += 1;
  shared.subscribers.add(callback);

  callback({
    lastMessage: shared.lastMessage,
    isConnected: shared.isConnected,
  });

  if (!shared.ws && !shared.reconnectTimer) {
    connectSharedSocket(shared);
  }

  return () => {
    shared.subscribers.delete(callback);
    shared.refCount = Math.max(0, shared.refCount - 1);

    if (shared.refCount === 0) {
      shared.closeTimer = setTimeout(() => {
        if (shared.refCount > 0) return;

        clearTimeout(shared.reconnectTimer);
        shared.reconnectTimer = null;

        if (shared.ws) {
          shared.ws.close();
          shared.ws = null;
        }

        shared.isConnected = false;
        shared.lastMessage = null;
        sharedSockets.delete(wsUrl);
      }, CLOSE_GRACE_MS);
    }
  };
}

/**
 * WebSocket hook for real-time updates from the Pi backend.
 *
 * Usage:
 *   const { lastMessage, isConnected } = useWebSocket("/ws/updates");
 *
 * Messages received:
 *   { type: "stock_update", product_id: 1, quantity: 5 }
 *   { type: "price_update", product_id: 1, sell_price: 2.50 }
 *   { type: "status", online: true }
 */
export default function useWebSocket(url) {
  const [lastMessage, setLastMessage] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}${url}`;

    const unsubscribe = subscribeSharedSocket(wsUrl, (snapshot) => {
      setLastMessage(snapshot.lastMessage);
      setIsConnected(snapshot.isConnected);
    });

    return unsubscribe;
  }, [url]);

  return { lastMessage, isConnected };
}
