import React from "react";
import VendingSlot from "./VendingSlot";

export default function VendingShelf({ row, products }) {
  return (
    <div className="flex gap-1">
      <div className="w-6 flex items-center justify-center text-xs text-gray-500 font-mono">
        {row}
      </div>
      <div className="flex-1 grid grid-cols-4 gap-1">
        {products.map((product) => (
          <VendingSlot key={product.id} product={product} />
        ))}
        {/* Fill empty slots if row has fewer than 4 */}
        {Array.from({ length: Math.max(0, 4 - products.length) }).map(
          (_, i) => (
            <div
              key={`empty-${i}`}
              className="bg-gray-800 rounded h-16 border border-gray-700 border-dashed"
            />
          )
        )}
      </div>
    </div>
  );
}
