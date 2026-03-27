import React, { useState } from "react";
import useTestRuns from "../hooks/useTestRuns";

/* -- Sub-components -- */

function ScenarioSelector({ scenarios, selected, onToggle }) {
  return (
    <div className="mb-6">
      <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
        Scenarios
      </h3>
      <div className="flex flex-wrap gap-2">
        {scenarios.map((s) => (
          <label
            key={s.name}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs cursor-pointer border transition-colors ${
              selected.includes(s.name)
                ? "bg-gray-900 border-gray-900 text-white"
                : "bg-white border-gray-200 text-gray-600 hover:border-gray-300"
            }`}
          >
            <input
              type="checkbox"
              className="sr-only"
              checked={selected.includes(s.name)}
              onChange={() => onToggle(s.name)}
            />
            {s.description || s.name}
            <span className="opacity-50">({s.step_count})</span>
          </label>
        ))}
      </div>
    </div>
  );
}

function RunListSidebar({ runs, activeRunId, onSelect }) {
  if (runs.length === 0) {
    return (
      <p className="text-xs text-gray-400 italic p-4">No runs yet</p>
    );
  }
  return (
    <ul className="space-y-1 p-2">
      {runs.map((r) => (
        <li key={r.id}>
          <button
            onClick={() => onSelect(r.id)}
            className={`w-full text-left px-4 py-3 rounded-xl text-sm transition-colors ${
              r.id === activeRunId
                ? "bg-gray-900 text-white"
                : "hover:bg-gray-50 text-gray-700"
            }`}
          >
            <span
              className={`font-mono text-xs ${
                r.id === activeRunId ? "text-gray-400" : "text-gray-400"
              }`}
            >
              #{r.id}
            </span>
            <div className="flex items-center gap-2 mt-1">
              <StatusBadge
                status={r.status}
                inverted={r.id === activeRunId}
              />
              <span
                className={`text-xs ${
                  r.id === activeRunId ? "text-gray-300" : "text-gray-500"
                }`}
              >
                {r.pass_count}P / {r.fail_count}F
              </span>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

function StatusBadge({ status, inverted = false }) {
  const colors = {
    passed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    running: "bg-yellow-100 text-yellow-700",
    pending: "bg-gray-100 text-gray-500",
    completed: "bg-blue-100 text-blue-700",
    cancelled: "bg-gray-100 text-gray-500",
    error: "bg-red-100 text-red-700",
  };

  const invertedColors = {
    passed: "bg-green-500/20 text-green-300",
    failed: "bg-red-500/20 text-red-300",
    running: "bg-yellow-500/20 text-yellow-300",
    pending: "bg-gray-500/20 text-gray-300",
    completed: "bg-blue-500/20 text-blue-300",
    cancelled: "bg-gray-500/20 text-gray-300",
    error: "bg-red-500/20 text-red-300",
  };

  const palette = inverted ? invertedColors : colors;

  return (
    <span
      className={`px-2 py-0.5 rounded-md text-xs font-medium ${
        palette[status] || palette.pending
      }`}
    >
      {status}
    </span>
  );
}

function StepIcon({ status }) {
  if (status === "passed")
    return <span className="text-green-500">&#10003;</span>;
  if (status === "failed")
    return <span className="text-red-500">&#10007;</span>;
  if (status === "error") return <span className="text-red-500">!</span>;
  if (status === "running")
    return <span className="text-yellow-500 animate-pulse">&#9654;</span>;
  return <span className="text-gray-300">&#9675;</span>;
}

function StepTimeline({ steps }) {
  if (!steps || steps.length === 0) {
    return <p className="text-xs text-gray-400 italic">No steps</p>;
  }
  return (
    <div className="space-y-3">
      {steps.map((step, i) => (
        <div key={i} className="flex items-start gap-3 text-sm">
          <div className="mt-0.5">
            <StepIcon status={step.status} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-800">{step.name}</span>
              <span className="text-xs text-gray-400">{step.duration_ms}ms</span>
            </div>
            {step.error && (
              <p className="text-xs text-red-500 mt-1">{step.error}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function ConversationView({ steps }) {
  const messages = (steps || []).filter(
    (s) => s.customer_message || s.agent_response
  );
  if (messages.length === 0) return null;

  return (
    <div className="mt-4 border border-gray-200 rounded-xl p-4 bg-gray-50">
      <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
        Conversation
      </h4>
      <div className="space-y-3 max-h-72 overflow-y-auto">
        {messages.map((s, i) => (
          <div key={i}>
            {s.customer_message && (
              <div className="flex gap-2 text-sm">
                <span className="shrink-0 text-gray-400">&#128100;</span>
                <p className="bg-white rounded-xl px-3 py-2 border border-gray-200 text-gray-700">
                  {s.customer_message}
                </p>
              </div>
            )}
            {s.agent_response && (
              <div className="flex gap-2 text-sm mt-2">
                <span className="shrink-0 text-gray-400">&#129302;</span>
                <p className="bg-gray-900 text-white rounded-xl px-3 py-2 text-gray-100">
                  {s.agent_response.slice(0, 300)}
                  {s.agent_response.length > 300 ? "..." : ""}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function AggregateStats({ runs }) {
  const totalRuns = runs.length;
  const totalScenarios = runs.reduce(
    (sum, r) => sum + r.pass_count + r.fail_count,
    0
  );
  const totalPass = runs.reduce((sum, r) => sum + r.pass_count, 0);
  const passRate =
    totalScenarios > 0 ? Math.round((totalPass / totalScenarios) * 100) : 0;

  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="bg-white rounded-2xl border border-gray-200/60 p-5 text-center">
        <p className="text-2xl font-semibold text-gray-900">{totalRuns}</p>
        <p className="text-xs text-gray-400 mt-1">Total Runs</p>
      </div>
      <div className="bg-white rounded-2xl border border-gray-200/60 p-5 text-center">
        <p className="text-2xl font-semibold text-gray-900">{totalScenarios}</p>
        <p className="text-xs text-gray-400 mt-1">Scenarios</p>
      </div>
      <div className="bg-white rounded-2xl border border-gray-200/60 p-5 text-center">
        <p
          className={`text-2xl font-semibold ${
            passRate >= 80 ? "text-green-600" : "text-red-600"
          }`}
        >
          {passRate}%
        </p>
        <p className="text-xs text-gray-400 mt-1">Pass Rate</p>
      </div>
    </div>
  );
}

/* -- Main Component -- */

export default function TestMonitorTab() {
  const {
    runs,
    scenarios,
    activeRun,
    setActiveRun,
    loading,
    startRun,
    stopRun,
    fetchRunDetail,
  } = useTestRuns();

  const [selectedScenarios, setSelectedScenarios] = useState([]);

  const toggleScenario = (name) => {
    setSelectedScenarios((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  };

  const handleStart = async () => {
    const result = await startRun(selectedScenarios);
    if (result) {
      setSelectedScenarios([]);
    }
  };

  const handleSelectRun = (runId) => {
    fetchRunDetail(runId);
  };

  if (loading) {
    return (
      <div className="text-center py-16 text-gray-400">Loading Test Lab...</div>
    );
  }

  const activeResults = activeRun?.results || [];

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Test Lab</h1>
          <p className="text-sm text-gray-400 mt-1">
            End-to-end scenario testing
          </p>
        </div>
        <div className="flex items-center gap-3">
          {activeRun?.status === "running" && (
            <button
              onClick={() => stopRun(activeRun.id)}
              className="bg-red-50 text-red-600 px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-red-100 transition-colors"
            >
              Stop
            </button>
          )}
          <button
            onClick={handleStart}
            className="bg-gray-900 text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-gray-800 shadow-sm transition-colors"
          >
            Start Test Run
          </button>
        </div>
      </div>

      {/* Scenario selector */}
      <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
        <ScenarioSelector
          scenarios={scenarios}
          selected={selectedScenarios}
          onToggle={toggleScenario}
        />
      </div>

      {/* Stats */}
      <AggregateStats runs={runs} />

      {/* Main layout */}
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* Left sidebar — run history */}
        <div className="bg-white rounded-2xl border border-gray-200/60 max-h-[600px] overflow-y-auto">
          <div className="px-5 pt-5 pb-2">
            <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Run History
            </h3>
          </div>
          <RunListSidebar
            runs={runs}
            activeRunId={activeRun?.id}
            onSelect={handleSelectRun}
          />
        </div>

        {/* Right — active run detail */}
        <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
          {!activeRun ? (
            <div className="text-center py-16">
              <p className="text-sm text-gray-400">
                Select a run or start a new one
              </p>
            </div>
          ) : (
            <div>
              <div className="flex items-center gap-3 mb-6">
                <span className="font-mono text-sm text-gray-400">
                  #{activeRun.id}
                </span>
                <StatusBadge status={activeRun.status} />
              </div>

              {/* Per-scenario results */}
              <div className="space-y-5">
                {activeResults.map((sr, idx) => (
                  <div
                    key={idx}
                    className="border border-gray-200 rounded-xl p-5"
                  >
                    <div className="flex items-center gap-3 mb-4">
                      <StatusBadge status={sr.status} />
                      <span className="font-medium text-sm text-gray-800">
                        {sr.scenario_name}
                      </span>
                    </div>
                    {sr.error && (
                      <p className="text-sm text-red-500 mb-3 bg-red-50 px-3 py-2 rounded-lg">
                        {sr.error}
                      </p>
                    )}
                    <StepTimeline steps={sr.steps} />
                    <ConversationView steps={sr.steps} />
                  </div>
                ))}
              </div>

              {activeResults.length === 0 && activeRun.status === "running" && (
                <p className="text-sm text-yellow-600 animate-pulse py-8 text-center">
                  Running scenarios...
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
