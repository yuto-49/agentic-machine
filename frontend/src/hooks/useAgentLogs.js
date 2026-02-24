import { useEffect, useRef, useState } from "react";

/**
 * Polls /api/admin/logs every `pollInterval` ms.
 * Returns { logs, loading, latestAction }.
 */
export default function useAgentLogs(pollInterval = 5000) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef(null);

  const fetchLogs = async () => {
    try {
      const res = await fetch("/api/admin/logs?limit=50");
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch {
      // Silently fail on poll errors — backend may not be running
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    timerRef.current = setInterval(fetchLogs, pollInterval);
    return () => clearInterval(timerRef.current);
  }, [pollInterval]);

  const latestAction = logs.length > 0 ? logs[0].action : null;

  return { logs, loading, latestAction };
}
