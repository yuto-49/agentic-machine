import React from "react";

function formatTime(dateStr) {
  try {
    return new Date(dateStr).toLocaleTimeString();
  } catch {
    return dateStr;
  }
}

export default function LogEntry({ log }) {
  const isBlocked = log.was_blocked;
  const isToolCall = /tool|set_price|get_inventory|unlock|restock|balance|send_message/i.test(
    log.action
  );

  const borderColor = isBlocked
    ? "border-red-500"
    : isToolCall
      ? "border-blue-500"
      : "border-gray-600";

  const bgColor = isBlocked
    ? "bg-red-950/50"
    : isToolCall
      ? "bg-blue-950/50"
      : "bg-gray-800";

  return (
    <div className={`p-2 rounded border-l-4 ${borderColor} ${bgColor}`}>
      <p className="text-xs font-medium text-gray-200 truncate">{log.action}</p>
      <p className="text-[10px] text-gray-400 mt-0.5 truncate">{log.trigger}</p>
      {log.reasoning && (
        <p className="text-[10px] text-gray-500 mt-0.5 line-clamp-2">
          {log.reasoning}
        </p>
      )}
      <p className="text-[10px] text-gray-600 mt-1">
        {formatTime(log.created_at)}
      </p>
    </div>
  );
}
