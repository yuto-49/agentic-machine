import React, { useEffect, useState } from "react";

export default function AdminDashboard() {
  const [analytics, setAnalytics] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/api/admin/analytics").then((r) => r.json()),
      fetch("/api/admin/logs?limit=20").then((r) => r.json()),
    ])
      .then(([analyticsData, logsData]) => {
        setAnalytics(analyticsData);
        setLogs(logsData);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-center py-8 text-gray-500">Loading admin data...</p>;

  return (
    <div className="space-y-6">
      {/* Analytics Summary */}
      {analytics && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">Analytics</h2>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-green-600">
                ${analytics.total_revenue?.toFixed(2) || "0.00"}
              </p>
              <p className="text-sm text-gray-500">Total Revenue</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-indigo-600">
                {analytics.total_items_sold || 0}
              </p>
              <p className="text-sm text-gray-500">Items Sold</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-800">
                {analytics.active_products || 0}
              </p>
              <p className="text-sm text-gray-500">Active Products</p>
            </div>
          </div>
        </div>
      )}

      {/* Agent Decision Logs */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4">Recent Agent Decisions</h2>
        {logs.length === 0 ? (
          <p className="text-gray-500">No decisions logged yet.</p>
        ) : (
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {logs.map((log) => (
              <div
                key={log.id}
                className={`p-3 rounded border-l-4 ${
                  log.was_blocked
                    ? "border-red-500 bg-red-50"
                    : "border-gray-300 bg-gray-50"
                }`}
              >
                <p className="text-sm font-medium">{log.action}</p>
                <p className="text-xs text-gray-500 mt-1">
                  Trigger: {log.trigger}
                </p>
                {log.reasoning && (
                  <p className="text-xs text-gray-400 mt-1">{log.reasoning}</p>
                )}
                <p className="text-xs text-gray-400 mt-1">{log.created_at}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
