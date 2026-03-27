import React, { useState, useEffect, useCallback } from "react";

const API = "/api/market-sim";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ status }) {
  const colors = {
    pending: "bg-gray-100 text-gray-600",
    seeding: "bg-blue-100 text-blue-700",
    generating: "bg-purple-100 text-purple-700",
    simulating: "bg-yellow-100 text-yellow-700",
    reporting: "bg-orange-100 text-orange-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  const labels = {
    pending: "Pending",
    seeding: "Seeding location…",
    generating: "Generating agents…",
    simulating: "Running swarm…",
    reporting: "Building report…",
    completed: "Completed",
    failed: "Failed",
  };
  return (
    <span className={`text-xs font-semibold px-2 py-1 rounded-full ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {labels[status] || status}
    </span>
  );
}

function TopProductsChart({ products }) {
  if (!products || products.length === 0) return null;
  const max = Math.max(...products.map((p) => p.projected_weekly_units || 1));
  return (
    <div className="space-y-2">
      {products.map((p, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="text-xs font-bold text-gray-400 w-4">#{p.rank}</span>
          <span className="text-sm text-gray-800 w-36 truncate">{p.product}</span>
          <div className="flex-1 bg-gray-100 rounded-full h-4">
            <div
              className="bg-indigo-500 h-4 rounded-full"
              style={{ width: `${((p.projected_weekly_units || 1) / max) * 100}%` }}
            />
          </div>
          <span className="text-xs text-gray-500 w-20 text-right">
            ~{p.projected_weekly_units ?? "?"} /wk
          </span>
        </div>
      ))}
    </div>
  );
}

function SegmentBreakdown({ segments }) {
  if (!segments || segments.length === 0) return null;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {segments.map((s, i) => (
        <div key={i} className="bg-gray-50 rounded-lg p-3 border border-gray-200">
          <div className="flex justify-between items-center mb-1">
            <span className="text-sm font-semibold text-gray-700">{s.segment}</span>
            <span className="text-xs text-indigo-600 font-bold">{s.share_pct}%</span>
          </div>
          <div className="text-xs text-gray-500">Top pick: <span className="font-medium text-gray-700">{s.top_product}</span></div>
          <div className="text-xs text-gray-500 mt-1">{s.insight}</div>
        </div>
      ))}
    </div>
  );
}

function RevenueForecast({ forecast }) {
  if (!forecast || !forecast.weekly_mid) return null;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {[
        { label: "Weekly (low)", value: forecast.weekly_low, color: "text-yellow-600" },
        { label: "Weekly (mid)", value: forecast.weekly_mid, color: "text-green-600" },
        { label: "Weekly (high)", value: forecast.weekly_high, color: "text-blue-600" },
        { label: "Monthly (mid)", value: forecast.monthly_mid, color: "text-purple-600" },
      ].map((item, i) => (
        <div key={i} className="bg-gray-50 rounded-lg p-3 border border-gray-200 text-center">
          <div className={`text-xl font-bold ${item.color}`}>
            ${item.value?.toLocaleString("en-US", { maximumFractionDigits: 0 }) ?? "—"}
          </div>
          <div className="text-xs text-gray-500 mt-1">{item.label}</div>
        </div>
      ))}
    </div>
  );
}

function ReportView({ sim }) {
  const report = sim.report || {};
  const seed = sim.seed || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-indigo-50 rounded-lg p-4 border border-indigo-200">
        <h3 className="font-bold text-indigo-800 text-lg mb-1">{seed.location_name}</h3>
        <div className="flex flex-wrap gap-2 text-xs text-indigo-600">
          <span className="bg-indigo-100 px-2 py-0.5 rounded">{seed.location_type}</span>
          <span className="bg-indigo-100 px-2 py-0.5 rounded">{seed.city}, {seed.country}</span>
          <span className="bg-indigo-100 px-2 py-0.5 rounded">{seed.daily_foot_traffic?.toLocaleString()} visitors/day</span>
          <span className={`px-2 py-0.5 rounded ${report.confidence_level === "high" ? "bg-green-100 text-green-700" : report.confidence_level === "medium" ? "bg-yellow-100 text-yellow-700" : "bg-red-100 text-red-700"}`}>
            {report.confidence_level} confidence
          </span>
        </div>
        {report.executive_summary && (
          <p className="text-sm text-gray-700 mt-3">{report.executive_summary}</p>
        )}
      </div>

      {/* Top Products */}
      <div>
        <h4 className="font-semibold text-gray-700 mb-3">Top Products</h4>
        <TopProductsChart products={sim.top_products} />
        <div className="mt-3 space-y-1">
          {(sim.top_products || []).map((p, i) => (
            <div key={i} className="text-xs text-gray-500">
              <span className="font-medium text-gray-700">#{p.rank} {p.product}:</span> {p.why}
            </div>
          ))}
        </div>
      </div>

      {/* Products to Add */}
      {report.products_to_add && report.products_to_add.length > 0 && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-2">Recommended Additions</h4>
          <div className="space-y-2">
            {report.products_to_add.map((p, i) => (
              <div key={i} className="flex gap-2 text-sm">
                <span className="text-green-500 mt-0.5">+</span>
                <span><span className="font-medium">{p.product_type}</span> — {p.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Placement */}
      {report.optimal_placement && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-2">Optimal Placement</h4>
          <div className="bg-green-50 border border-green-200 rounded-lg p-3">
            <div className="font-semibold text-green-800">{report.optimal_placement.recommended_zone}</div>
            <div className="text-sm text-gray-600 mt-1">{report.optimal_placement.rationale}</div>
            {report.optimal_placement.runner_up_zone && (
              <div className="text-xs text-gray-400 mt-1">Runner-up: {report.optimal_placement.runner_up_zone}</div>
            )}
          </div>
        </div>
      )}

      {/* Revenue Forecast */}
      <div>
        <h4 className="font-semibold text-gray-700 mb-3">Revenue Forecast</h4>
        <RevenueForecast forecast={sim.revenue_forecast} />
      </div>

      {/* Segments */}
      <div>
        <h4 className="font-semibold text-gray-700 mb-3">Customer Segments</h4>
        <SegmentBreakdown segments={sim.segments} />
      </div>

      {/* Pricing recommendations */}
      {report.pricing_recommendations && report.pricing_recommendations.length > 0 && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-2">Pricing Recommendations</h4>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-xs text-gray-400 border-b">
                <th className="text-left py-1">Product</th>
                <th className="text-right py-1">Current</th>
                <th className="text-right py-1">Recommended</th>
                <th className="text-left py-1 pl-3">Reason</th>
              </tr>
            </thead>
            <tbody>
              {report.pricing_recommendations.map((r, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-1.5 text-gray-700">{r.product}</td>
                  <td className="py-1.5 text-right text-gray-500">${r.current_price?.toFixed(2)}</td>
                  <td className={`py-1.5 text-right font-semibold ${r.recommended_price > r.current_price ? "text-green-600" : "text-red-600"}`}>
                    ${r.recommended_price?.toFixed(2)}
                  </td>
                  <td className="py-1.5 pl-3 text-gray-500 text-xs">{r.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Risks */}
      {report.risk_factors && report.risk_factors.length > 0 && (
        <div>
          <h4 className="font-semibold text-gray-700 mb-2">Risk Factors</h4>
          <ul className="space-y-1">
            {report.risk_factors.map((r, i) => (
              <li key={i} className="text-sm text-gray-600 flex gap-2">
                <span className="text-yellow-500 mt-0.5">⚠</span>{r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function MarketSimRunner() {
  const [location, setLocation] = useState("");
  const [agentCount, setAgentCount] = useState(200);
  const [running, setRunning] = useState(false);
  const [activeSim, setActiveSim] = useState(null);
  const [history, setHistory] = useState([]);
  const [pollingId, setPollingId] = useState(null);
  const [activeTab, setActiveTab] = useState("run"); // run | history

  // Fetch history
  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(API);
      if (res.ok) setHistory(await res.json());
    } catch (_) {}
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Poll active simulation
  useEffect(() => {
    if (!pollingId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API}/${pollingId}`);
        if (!res.ok) return;
        const data = await res.json();
        setActiveSim(data);
        if (data.status === "completed" || data.status === "failed") {
          clearInterval(interval);
          setRunning(false);
          setPollingId(null);
          loadHistory();
        }
      } catch (_) {}
    }, 3000);
    return () => clearInterval(interval);
  }, [pollingId, loadHistory]);

  const handleRun = async () => {
    if (!location.trim()) return;
    setRunning(true);
    setActiveSim(null);
    try {
      const res = await fetch(`${API}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ location: location.trim(), agent_count: agentCount }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setActiveSim({ simulation_id: data.simulation_id, location: location.trim(), status: "pending", agent_count: agentCount });
      setPollingId(data.simulation_id);
      setActiveTab("run");
    } catch (err) {
      alert(`Failed to start simulation: ${err.message}`);
      setRunning(false);
    }
  };

  const loadHistorySim = async (id) => {
    const res = await fetch(`${API}/${id}`);
    if (res.ok) {
      setActiveSim(await res.json());
      setActiveTab("run");
    }
  };

  const EXAMPLE_LOCATIONS = [
    "University of Tokyo Hongo Campus, Japan",
    "Google HQ Mountain View, California",
    "Shibuya Station, Tokyo",
    "MIT Campus, Cambridge MA",
    "Westfield Shopping Centre, London",
  ];

  const progressSteps = ["pending", "seeding", "generating", "simulating", "reporting", "completed"];
  const stepIndex = activeSim ? progressSteps.indexOf(activeSim.status) : -1;

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Market Prediction Simulator</h2>
        <p className="text-sm text-gray-500 mt-1">
          Simulate hundreds of autonomous customer agents at any real-world location to predict
          product demand, optimal placement, and revenue.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        {["run", "history"].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${
              activeTab === tab
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab === "run" ? "Simulation" : "History"}
          </button>
        ))}
      </div>

      {activeTab === "run" && (
        <div className="space-y-6">
          {/* Input form */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Location
              </label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. University of Tokyo Hongo Campus"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                disabled={running}
              />
              <div className="flex flex-wrap gap-2 mt-2">
                {EXAMPLE_LOCATIONS.map((loc) => (
                  <button
                    key={loc}
                    onClick={() => setLocation(loc)}
                    className="text-xs text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-2 py-1 rounded-full"
                    disabled={running}
                  >
                    {loc.split(",")[0]}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Synthetic Agents: <span className="text-indigo-600 font-bold">{agentCount}</span>
              </label>
              <input
                type="range"
                min={10}
                max={500}
                step={10}
                value={agentCount}
                onChange={(e) => setAgentCount(Number(e.target.value))}
                className="w-full"
                disabled={running}
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>10 (fast)</span>
                <span>500 (thorough)</span>
              </div>
            </div>

            <button
              onClick={handleRun}
              disabled={running || !location.trim()}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white font-semibold py-2 rounded-lg transition-colors"
            >
              {running ? "Simulating…" : "Run Simulation"}
            </button>
          </div>

          {/* Progress */}
          {activeSim && activeSim.status !== "completed" && activeSim.status !== "failed" && (
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <span className="font-medium text-gray-700">{activeSim.location}</span>
                <StatusBadge status={activeSim.status} />
              </div>
              <div className="flex items-center gap-1">
                {progressSteps.slice(0, -1).map((step, i) => (
                  <React.Fragment key={step}>
                    <div className={`flex-1 h-1.5 rounded-full ${i <= stepIndex ? "bg-indigo-500" : "bg-gray-200"}`} />
                  </React.Fragment>
                ))}
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>Seed</span>
                <span>Agents</span>
                <span>Swarm</span>
                <span>Report</span>
              </div>
              {activeSim.status === "simulating" && (
                <p className="text-sm text-gray-500 mt-3">
                  Running {activeSim.agent_count} agents in parallel — this takes ~30-90 seconds…
                </p>
              )}
            </div>
          )}

          {/* Failed */}
          {activeSim && activeSim.status === "failed" && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-red-700">
              Simulation failed. Check server logs for details.
            </div>
          )}

          {/* Results */}
          {activeSim && activeSim.status === "completed" && (
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <ReportView sim={activeSim} />
            </div>
          )}
        </div>
      )}

      {activeTab === "history" && (
        <div className="space-y-3">
          {history.length === 0 && (
            <p className="text-sm text-gray-400">No simulations yet.</p>
          )}
          {history.map((s) => (
            <div
              key={s.simulation_id}
              className="bg-white border border-gray-200 rounded-lg p-4 flex items-center justify-between hover:border-indigo-300 cursor-pointer"
              onClick={() => loadHistorySim(s.simulation_id)}
            >
              <div>
                <div className="font-medium text-gray-800 text-sm">{s.location}</div>
                {s.placement_recommendation && (
                  <div className="text-xs text-gray-400 mt-0.5">
                    Placement: {s.placement_recommendation}
                  </div>
                )}
                <div className="text-xs text-gray-400 mt-0.5">
                  {s.agent_count} agents · {new Date(s.created_at).toLocaleDateString()}
                </div>
              </div>
              <StatusBadge status={s.status} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
