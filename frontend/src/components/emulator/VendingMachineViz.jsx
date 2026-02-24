import React, { useContext } from "react";
import { EmulatorContext } from "../../context/EmulatorContext";
import VendingShelf from "./VendingShelf";
import HardwareStatusPanel from "./HardwareStatusPanel";

function groupByShelfRow(products) {
  const shelves = {};
  for (const p of products) {
    if (!p.slot) continue;
    const row = p.slot.charAt(0);
    if (!shelves[row]) shelves[row] = [];
    shelves[row].push(p);
  }
  for (const row of Object.keys(shelves)) {
    shelves[row].sort((a, b) => a.slot.localeCompare(b.slot));
  }
  return shelves;
}

export default function VendingMachineViz() {
  const { products, productsLoading, hardwareStatus, wsConnected } =
    useContext(EmulatorContext);

  const shelves = groupByShelfRow(products);

  return (
    <div className="p-4 text-white h-full flex flex-col">
      <h2 className="text-lg font-bold mb-1 text-center">Physical Machine</h2>
      <p className="text-[10px] text-center mb-3">
        <span
          className={`inline-block w-1.5 h-1.5 rounded-full mr-1 ${wsConnected ? "bg-green-500" : "bg-gray-500"}`}
        />
        <span className="text-gray-400">
          {wsConnected ? "WebSocket connected" : "WebSocket disconnected"}
        </span>
      </p>

      {/* Machine body */}
      <div className="bg-gray-800 rounded-xl border border-gray-600 p-3 flex-1">
        {/* Glass front / shelves area */}
        <div className="bg-gray-900 rounded-lg p-2 border border-gray-700 space-y-2">
          {productsLoading ? (
            <p className="text-gray-500 text-sm text-center py-8">
              Loading inventory...
            </p>
          ) : Object.keys(shelves).length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-8">
              No products stocked
            </p>
          ) : (
            Object.entries(shelves).map(([row, slotProducts]) => (
              <VendingShelf key={row} row={row} products={slotProducts} />
            ))
          )}
        </div>

        {/* Dispensing bay */}
        <div className="mt-3 bg-gray-950 rounded-lg h-12 border border-gray-700 flex items-center justify-center text-gray-500 text-xs select-none">
          PICKUP
        </div>
      </div>

      {/* Hardware status indicators */}
      <HardwareStatusPanel status={hardwareStatus} />
    </div>
  );
}
