import { useCallback, useEffect, useState } from "react";
import useWebSocket from "./useWebSocket";

/**
 * Fetches product requests from /api/requests on mount, then applies
 * real-time WebSocket updates for new requests and status changes.
 */
export default function useProductRequests() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { lastMessage, isConnected } = useWebSocket("/ws/updates");

  useEffect(() => {
    fetch("/api/requests")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setRequests)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // Apply WebSocket updates
  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === "new_product_request") {
      setRequests((prev) => [lastMessage.request, ...prev]);
    }

    if (lastMessage.type === "request_status_update") {
      setRequests((prev) =>
        prev.map((r) =>
          r.id === lastMessage.request_id
            ? { ...r, status: lastMessage.status, notes: lastMessage.notes }
            : r
        )
      );
    }
  }, [lastMessage]);

  const updateRequest = useCallback(async (id, data) => {
    const res = await fetch(`/api/requests/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const updated = await res.json();
    setRequests((prev) =>
      prev.map((r) => (r.id === id ? updated : r))
    );
    return updated;
  }, []);

  return { requests, loading, error, updateRequest, wsConnected: isConnected };
}
