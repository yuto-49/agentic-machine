import React, { useContext, useEffect, useState } from "react";
import { EmulatorContext } from "../context/EmulatorContext";

function StatCard({ label, value, sub, valueColor = "text-gray-900" }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
        {label}
      </p>
      <p className={`text-3xl font-semibold mt-3 ${valueColor}`}>{value}</p>
      <p className="text-xs text-gray-400 mt-2">{sub}</p>
    </div>
  );
}

export default function DashboardHome() {
  const { products, productsLoading, wsConnected, logs } =
    useContext(EmulatorContext);
  const [analytics, setAnalytics] = useState(null);

  useEffect(() => {
    fetch("/api/admin/analytics")
      .then((r) => r.json())
      .then(setAnalytics)
      .catch(console.error);
  }, []);

  const totalStock = products.reduce((sum, p) => sum + (p.quantity || 0), 0);
  const activeProducts = products.filter((p) => p.quantity > 0).length;

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-400 mt-1">
          Overview of your vending machine
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          label="Revenue"
          value={
            analytics
              ? `$${analytics.total_revenue?.toFixed(2) || "0.00"}`
              : "\u2014"
          }
          sub="All time"
        />
        <StatCard
          label="Items Sold"
          value={analytics?.total_items_sold ?? "\u2014"}
          sub="All time"
        />
        <StatCard
          label="Products"
          value={activeProducts}
          sub={`${totalStock} total units in stock`}
        />
        <StatCard
          label="Status"
          value={wsConnected ? "Online" : "Offline"}
          sub="Machine connection"
          valueColor={wsConnected ? "text-green-600" : "text-red-500"}
        />
      </div>

      {/* Two-column: Inventory + Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Inventory snapshot */}
        <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
          <h2 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-5">
            Inventory
          </h2>
          {productsLoading ? (
            <p className="text-sm text-gray-400 py-4">Loading...</p>
          ) : products.length === 0 ? (
            <p className="text-sm text-gray-400 py-4">
              No products configured
            </p>
          ) : (
            <div className="space-y-3">
              {products.slice(0, 12).map((p) => (
                <div
                  key={p.id}
                  className="flex items-center justify-between py-1"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-xs font-mono text-gray-400 w-6 shrink-0">
                      {p.slot}
                    </span>
                    <span className="text-sm text-gray-800 truncate">
                      {p.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0 ml-4">
                    <span className="text-sm text-gray-500">
                      ${p.sell_price?.toFixed(2)}
                    </span>
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        p.quantity > 5
                          ? "bg-green-50 text-green-700"
                          : p.quantity > 0
                          ? "bg-amber-50 text-amber-700"
                          : "bg-red-50 text-red-600"
                      }`}
                    >
                      {p.quantity}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent agent activity */}
        <div className="bg-white rounded-2xl border border-gray-200/60 p-6">
          <h2 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-5">
            Recent Activity
          </h2>
          {logs.length === 0 ? (
            <p className="text-sm text-gray-400 py-4">
              No agent activity yet. Interact with the machine to see logs here.
            </p>
          ) : (
            <div className="space-y-3">
              {logs.slice(0, 8).map((log) => (
                <div
                  key={log.id}
                  className={`rounded-xl p-4 ${
                    log.was_blocked
                      ? "bg-red-50 border border-red-100"
                      : "bg-gray-50"
                  }`}
                >
                  <p className="text-sm font-medium text-gray-800">
                    {log.action}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">{log.trigger}</p>
                  {log.reasoning && (
                    <p className="text-xs text-gray-400 mt-1 line-clamp-2">
                      {log.reasoning}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
