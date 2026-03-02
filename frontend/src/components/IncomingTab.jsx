import React from "react";
import useProductRequests from "../hooks/useProductRequests";

const STATUS_COLORS = {
  pending: "bg-yellow-100 text-yellow-800",
  approved: "bg-blue-100 text-blue-800",
  ordered: "bg-purple-100 text-purple-800",
  arrived: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

export default function IncomingTab() {
  const { requests, loading, error } = useProductRequests();

  if (loading) {
    return <p className="text-center text-gray-500 py-8">Loading requests...</p>;
  }

  if (error) {
    return <p className="text-center text-red-500 py-8">Error: {error}</p>;
  }

  if (requests.length === 0) {
    return (
      <p className="text-center text-gray-400 py-8">
        No product requests yet. Ask Claudius on Slack to find something!
      </p>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {requests.map((req) => (
        <div
          key={req.id}
          className="bg-white rounded-lg shadow p-4 flex gap-4"
        >
          {req.image_url && (
            <img
              src={req.image_url}
              alt={req.product_name}
              className="w-20 h-20 object-cover rounded"
            />
          )}
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">
              {req.product_name}
            </h3>
            {req.estimated_price != null && (
              <p className="text-indigo-600 font-medium">
                ${req.estimated_price.toFixed(2)}
              </p>
            )}
            <p className="text-xs text-gray-500 truncate">
              Requested by {req.requested_by || "unknown"}
              {req.platform && ` via ${req.platform}`}
            </p>
            <div className="mt-2 flex items-center gap-2">
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                  STATUS_COLORS[req.status] || "bg-gray-100 text-gray-600"
                }`}
              >
                {req.status}
              </span>
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
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
