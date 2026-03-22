import { useState, useEffect, useCallback } from "react";

const API_BASE = "/api";

export function useScenarioPresets() {
  const [presets, setPresets] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/scenario/presets`)
      .then((res) => res.json())
      .then(setPresets)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return { presets, loading };
}

export function useScenarioRun() {
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  const run = useCallback(async (prompt, presetId = null) => {
    setRunning(true);
    setError(null);
    setResult(null);

    try {
      const body = { prompt };
      if (presetId) body.preset_id = presetId;

      const res = await fetch(`${API_BASE}/scenario/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Simulation failed");
      }

      const data = await res.json();
      setResult(data);
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setRunning(false);
    }
  }, []);

  return { run, result, running, error };
}

export function useScenarioHistory() {
  const [scenarios, setScenarios] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    fetch(`${API_BASE}/scenario`)
      .then((res) => res.json())
      .then(setScenarios)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { scenarios, loading, refresh };
}
