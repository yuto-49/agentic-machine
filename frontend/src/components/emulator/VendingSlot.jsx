import React from "react";
import StockLevelBar from "./StockLevelBar";

export default function VendingSlot({ product }) {
  const fillPercent =
    product.max_quantity > 0
      ? Math.round((product.quantity / product.max_quantity) * 100)
      : 0;
  const isEmpty = product.quantity === 0;

  return (
    <div
      className={`relative bg-gray-800 rounded p-1.5 border h-16 flex flex-col justify-between ${
        isEmpty ? "border-red-800 opacity-60" : "border-gray-600"
      }`}
    >
      <span className="text-[9px] font-mono text-gray-400">{product.slot}</span>
      <span className="text-[10px] text-gray-200 leading-tight truncate">
        {product.name}
      </span>
      <StockLevelBar percent={fillPercent} quantity={product.quantity} />
    </div>
  );
}
