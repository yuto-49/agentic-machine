import React, { useEffect, useState } from "react";
import useProductRequests from "../hooks/useProductRequests";

const STATUS_COLORS = {
  pending: "bg-yellow-100 text-yellow-800",
  approved: "bg-blue-100 text-blue-800",
  ordered: "bg-purple-100 text-purple-800",
  arrived: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

/* ── Admin action buttons per request status ── */

function RequestActions({ req, onUpdate }) {
  const [busy, setBusy] = useState(false);

  const handle = async (status) => {
    setBusy(true);
    try {
      await onUpdate(req.id, { status });
    } finally {
      setBusy(false);
    }
  };

  if (busy) {
    return <span className="text-xs text-gray-400">Updating...</span>;
  }

  switch (req.status) {
    case "pending":
      return (
        <div className="flex gap-2">
          <button
            onClick={() => handle("approved")}
            className="text-sm px-3 py-1 rounded bg-green-500 text-white hover:bg-green-600"
          >
            Approve
          </button>
          <button
            onClick={() => handle("rejected")}
            className="text-sm px-3 py-1 rounded bg-red-500 text-white hover:bg-red-600"
          >
            Reject
          </button>
        </div>
      );
    case "approved":
      return (
        <button
          onClick={() => handle("ordered")}
          className="text-sm px-3 py-1 rounded bg-purple-500 text-white hover:bg-purple-600"
        >
          Mark Ordered
        </button>
      );
    case "ordered":
      return (
        <button
          onClick={() => handle("arrived")}
          className="text-sm px-3 py-1 rounded bg-green-500 text-white hover:bg-green-600"
        >
          Mark Arrived
        </button>
      );
    default:
      return null;
  }
}

/* ── Notes inline editor ── */

function NotesInput({ req, onUpdate }) {
  const [value, setValue] = useState(req.notes || "");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (value === (req.notes || "")) return;
    setSaving(true);
    try {
      await onUpdate(req.id, { notes: value });
    } finally {
      setSaving(false);
    }
  };

  return (
    <input
      type="text"
      placeholder="Add a note..."
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={save}
      onKeyDown={(e) => e.key === "Enter" && save()}
      disabled={saving}
      className="w-full text-xs border border-gray-200 rounded px-2 py-1 mt-1 focus:outline-none focus:ring-1 focus:ring-indigo-400"
    />
  );
}

/* ── Product Requests management section ── */

function RequestManagement() {
  const { requests, loading, error, updateRequest } = useProductRequests();
  const [filter, setFilter] = useState("all");

  const filtered =
    filter === "all"
      ? requests
      : requests.filter((r) => r.status === filter);

  if (loading) {
    return <p className="text-gray-500 text-sm">Loading requests...</p>;
  }
  if (error) {
    return <p className="text-red-500 text-sm">Error: {error}</p>;
  }

  return (
    <div>
      {/* Status filter tabs */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {["all", "pending", "approved", "ordered", "arrived", "rejected"].map(
          (s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`text-xs px-3 py-1 rounded-full capitalize ${
                filter === s
                  ? "bg-indigo-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {s}
              {s !== "all" && (
                <span className="ml-1">
                  ({requests.filter((r) => r.status === s).length})
                </span>
              )}
              {s === "all" && <span className="ml-1">({requests.length})</span>}
            </button>
          )
        )}
      </div>

      {filtered.length === 0 ? (
        <p className="text-gray-400 text-sm py-4">No requests match this filter.</p>
      ) : (
        <div className="space-y-3">
          {filtered.map((req) => (
            <div
              key={req.id}
              className="bg-gray-50 rounded-lg border p-4 flex gap-4"
            >
              {req.image_url && (
                <img
                  src={req.image_url}
                  alt={req.product_name}
                  className="w-16 h-16 object-cover rounded"
                />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h4 className="font-semibold text-gray-900 truncate">
                      {req.product_name}
                    </h4>
                    <p className="text-sm text-gray-500">
                      {req.estimated_price != null && (
                        <span className="text-indigo-600 font-medium mr-2">
                          ${req.estimated_price.toFixed(2)}
                        </span>
                      )}
                      by {req.requested_by || "unknown"}
                      {req.platform && ` via ${req.platform}`}
                    </p>
                  </div>
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${
                      STATUS_COLORS[req.status] || "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {req.status}
                  </span>
                </div>

                {req.source_url && (
                  <a
                    href={req.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-indigo-500 hover:underline"
                  >
                    View source
                  </a>
                )}

                {req.notes && (
                  <p className="text-xs text-gray-400 italic mt-1">{req.notes}</p>
                )}

                <div className="mt-2 flex items-center gap-3">
                  <RequestActions req={req} onUpdate={updateRequest} />
                </div>
                <NotesInput req={req} onUpdate={updateRequest} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Main Admin Dashboard ── */

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

      {/* Product Request Management */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4">Product Requests</h2>
        <RequestManagement />
      </div>

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
