import React from "react";

/**
 * CSS "monitor/laptop" bezel for the admin panel.
 * Visually distinct from IPadFrame — wider, rectangular, with a stand base.
 */
export default function MonitorFrame({ children }) {
  return (
    <div className="relative flex flex-col items-center">
      {/* Monitor outer shell */}
      <div
        className="bg-gray-800 rounded-lg p-3 shadow-2xl border-2 border-gray-600 flex flex-col"
        style={{ width: "100%", maxWidth: 520, height: 580 }}
      >
        {/* Header bar */}
        <div className="flex items-center justify-between px-3 py-1.5 mb-2 bg-gray-700 rounded shrink-0">
          <div className="flex gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
          </div>
          <span className="text-gray-300 text-xs font-medium tracking-wide">
            Admin Panel
          </span>
          <div className="w-14" /> {/* spacer for centering */}
        </div>

        {/* Screen area */}
        <div className="bg-white rounded overflow-hidden flex-1 min-h-0">
          <div className="h-full overflow-y-auto">{children}</div>
        </div>
      </div>

      {/* Monitor stand */}
      <div className="flex flex-col items-center">
        <div className="w-8 h-4 bg-gray-700 rounded-b-sm" />
        <div className="w-28 h-2 bg-gray-700 rounded-b-lg" />
      </div>
    </div>
  );
}
