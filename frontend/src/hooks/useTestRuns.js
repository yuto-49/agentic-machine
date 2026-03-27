import { useCallback, useEffect, useRef, useState } from "react";
import useWebSocket from "./useWebSocket";

/**
 * Hook for managing E2E test runs via /api/testing/* endpoints.
 * Fetches runs on mount, applies WebSocket live updates.
 */
export default function useTestRuns(pollInterval = 5000) {
  const [runs, setRuns] = useState([]);
  const [scenarios, setScenarios] = useState([]);
  const [activeRun, setActiveRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef(null);
  const { lastMessage } = useWebSocket("/ws/updates");

  // Fetch available scenarios
  useEffect(() => {
    fetch("/api/testing/scenarios")
      .then((res) => (res.ok ? res.json() : []))
      .then(setScenarios)
      .catch(() => {});
  }, []);

  // Fetch runs list
  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch("/api/testing/runs");
      if (res.ok) {
        const data = await res.json();
        setRuns(data);
      }
    } catch {
      // Backend may not be running
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRuns();
    timerRef.current = setInterval(fetchRuns, pollInterval);
    return () => clearInterval(timerRef.current);
  }, [fetchRuns, pollInterval]);

  // Apply WebSocket test updates
  useEffect(() => {
    if (!lastMessage) return;

    if (
      lastMessage.type === "test_update" ||
      lastMessage.type === "test_scenario_complete"
    ) {
      // Refresh the active run detail
      if (activeRun?.id === lastMessage.run_id) {
        fetchRunDetail(lastMessage.run_id);
      }
      fetchRuns();
    }
  }, [lastMessage]);

  const fetchRunDetail = useCallback(async (runId) => {
    try {
      const res = await fetch(`/api/testing/runs/${runId}`);
      if (res.ok) {
        const data = await res.json();
        setActiveRun(data);
      }
    } catch {
      // Ignore
    }
  }, []);

  const startRun = useCallback(async (selectedScenarios = []) => {
    try {
      const res = await fetch("/api/testing/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenarios: selectedScenarios }),
      });
      if (res.ok) {
        const data = await res.json();
        // Auto-select the new run
        fetchRunDetail(data.run_id);
        fetchRuns();
        return data;
      }
    } catch (err) {
      console.error("Failed to start test run:", err);
    }
    return null;
  }, [fetchRunDetail, fetchRuns]);

  const stopRun = useCallback(async (runId) => {
    try {
      await fetch(`/api/testing/runs/${runId}/stop`, { method: "POST" });
      fetchRuns();
    } catch {
      // Ignore
    }
  }, [fetchRuns]);

  return {
    runs,
    scenarios,
    activeRun,
    setActiveRun,
    loading,
    startRun,
    stopRun,
    fetchRunDetail,
  };
}
