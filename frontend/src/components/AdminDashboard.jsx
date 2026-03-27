import React, { useEffect, useState } from "react";
import useProductRequests from "../hooks/useProductRequests";

const STATUS_COLORS = {
  pending: "bg-yellow-100 text-yellow-800",
  approved: "bg-blue-100 text-blue-800",
  ordered: "bg-purple-100 text-purple-800",
  arrived: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

/* -- Admin action buttons per request status -- */

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
            className="text-sm px-4 py-1.5 rounded-lg bg-green-500 text-white hover:bg-green-600 transition-colors"
          >
            Approve
          </button>
          <button
            onClick={() => handle("rejected")}
            className="text-sm px-4 py-1.5 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
          >
            Reject
          </button>
        </div>
      );
    case "approved":
      return (
        <button
          onClick={() => handle("ordered")}
          className="text-sm px-4 py-1.5 rounded-lg bg-purple-500 text-white hover:bg-purple-600 transition-colors"
        >
          Mark Ordered
        </button>
      );
    case "ordered":
      return (
        <button
          onClick={() => handle("arrived")}
          className="text-sm px-4 py-1.5 rounded-lg bg-green-500 text-white hover:bg-green-600 transition-colors"
        >
          Mark Arrived
        </button>
      );
    default:
      return null;
  }
}

/* -- Notes inline editor -- */

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
      className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 mt-2 focus:outline-none focus:ring-2 focus:ring-gray-900/10 bg-white"
    />
  );
}

/* -- Product Requests management section -- */

function RequestManagement() {
  const { requests, loading, error, updateRequest } = useProductRequests();
  const [filter, setFilter] = useState("all");

  const filtered =
    filter === "all"
      ? requests
      : requests.filter((r) => r.status === filter);

  if (loading) {
    return <p className="text-gray-400 text-sm py-4">Loading requests...</p>;
  }
  if (error) {
    return <p className="text-red-500 text-sm py-4">Error: {error}</p>;
  }

  return (
    <div>
      {/* Status filter tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {["all", "pending", "approved", "ordered", "arrived", "rejected"].map(
          (s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`text-xs px-4 py-1.5 rounded-full capitalize transition-colors ${
                filter === s
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {s}
              <span className="ml-1 opacity-60">
                (
                {s === "all"
                  ? requests.length
                  : requests.filter((r) => r.status === s).length}
                )
              </span>
            </button>
          )
        )}
      </div>

      {filtered.length === 0 ? (
        <p className="text-gray-400 text-sm py-6">
          No requests match this filter.
        </p>
      ) : (
        <div className="space-y-4">
          {filtered.map((req) => (
            <div
              key={req.id}
              className="bg-gray-50 rounded-xl border border-gray-100 p-5 flex gap-5"
            >
              {req.image_url && (
                <img
                  src={req.image_url}
                  alt={req.product_name}
                  className="w-20 h-20 object-cover rounded-xl shrink-0"
                />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h4 className="font-semibold text-gray-900 text-base">
                      {req.product_name}
                    </h4>
                    <p className="text-sm text-gray-500 mt-1">
                      {req.estimated_price != null && (
                        <span className="text-gray-900 font-medium mr-2">
                          ${req.estimated_price.toFixed(2)}
                        </span>
                      )}
                      by {req.requested_by || "unknown"}
                      {req.platform && ` via ${req.platform}`}
                    </p>
                  </div>
                  <span
                    className={`text-xs font-medium px-2.5 py-1 rounded-full whitespace-nowrap ${
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
                    className="text-xs text-gray-500 hover:text-gray-700 hover:underline mt-1 inline-block"
                  >
                    View source
                  </a>
                )}

                {req.notes && (
                  <p className="text-xs text-gray-400 italic mt-2">
                    {req.notes}
                  </p>
                )}

                <div className="mt-3">
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

/* -- Main Admin Dashboard -- */

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

  if (loading)
    return (
      <p className="text-center py-12 text-gray-400">Loading admin data...</p>
    );

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Admin</h1>
        <p className="text-sm text-gray-400 mt-1">
          Analytics, product requests, and agent decisions
        </p>
      </div>

      {/* Analytics Summary */}
      {analytics && (
        <div className="grid grid-cols-3 gap-5">
          <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Total Revenue
            </p>
            <p className="text-3xl font-semibold text-green-600 mt-3">
              ${analytics.total_revenue?.toFixed(2) || "0.00"}
            </p>
          </div>
          <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Items Sold
            </p>
            <p className="text-3xl font-semibold text-gray-900 mt-3">
              {analytics.total_items_sold || 0}
            </p>
          </div>
          <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Active Products
            </p>
            <p className="text-3xl font-semibold text-gray-900 mt-3">
              {analytics.active_products || 0}
            </p>
          </div>
        </div>
      )}

      {/* Product Request Management */}
      <div className="bg-white rounded-2xl border border-gray-200/60 p-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">
          Product Requests
        </h2>
        <RequestManagement />
      </div>

      {/* Agent Decision Logs */}
      <div className="bg-white rounded-2xl border border-gray-200/60 p-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">
          Recent Agent Decisions
        </h2>
        {logs.length === 0 ? (
          <p className="text-gray-400 text-sm py-4">
            No decisions logged yet.
          </p>
        ) : (
          <div className="space-y-3 max-h-[500px] overflow-y-auto">
            {logs.map((log) => (
              <div
                key={log.id}
                className={`p-4 rounded-xl border-l-4 ${
                  log.was_blocked
                    ? "border-red-400 bg-red-50"
                    : "border-gray-200 bg-gray-50"
                }`}
              >
                <p className="text-sm font-medium text-gray-800">
                  {log.action}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Trigger: {log.trigger}
                </p>
                {log.reasoning && (
                  <p className="text-xs text-gray-400 mt-1">{log.reasoning}</p>
                )}
                <p className="text-xs text-gray-400 mt-2">{log.created_at}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
