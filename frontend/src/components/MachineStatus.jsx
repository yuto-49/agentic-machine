import React, { useEffect, useState } from "react";

export default function MachineStatus() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/status")
      .then((res) => res.json())
      .then(setStatus)
      .catch(() => setStatus({ status: "offline" }))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-center py-8 text-gray-500">Checking status...</p>;

  const isOnline = status?.status === "online";

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold mb-4">Machine Status</h2>

      <div className="flex items-center gap-3 mb-4">
        <span
          className={`w-3 h-3 rounded-full ${isOnline ? "bg-green-500" : "bg-red-500"}`}
        />
        <span className="font-medium">
          {isOnline ? "Online" : "Offline"}
        </span>
      </div>

      {status && (
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="text-gray-500">Version</dt>
          <dd>{status.version || "—"}</dd>
          <dt className="text-gray-500">Environment</dt>
          <dd>{status.environment || "—"}</dd>
        </dl>
      )}
    </div>
  );
}
