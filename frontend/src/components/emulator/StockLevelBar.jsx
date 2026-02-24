import React from "react";

export default function StockLevelBar({ percent, quantity }) {
  const color =
    percent > 50
      ? "bg-green-500"
      : percent > 20
        ? "bg-yellow-500"
        : "bg-red-500";

  return (
    <div className="flex items-center gap-1">
      <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-[8px] text-gray-400 w-4 text-right">{quantity}</span>
    </div>
  );
}
