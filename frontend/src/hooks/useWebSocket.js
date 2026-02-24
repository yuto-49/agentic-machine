import { useEffect, useRef, useState } from "react";

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
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  useEffect(() => {
    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}${url}`;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
        } catch {
          // Ignore non-JSON messages
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        // Reconnect after 3 seconds
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    }

    connect();

    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [url]);

  return { lastMessage, isConnected };
}
