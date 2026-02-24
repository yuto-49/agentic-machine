import React from "react";

/**
 * Pure-CSS iPad bezel that wraps its children (the App component).
 * Sized to approximate an iPad Mini in portrait.
 */
export default function IPadFrame({ children }) {
  return (
    <div className="relative flex flex-col items-center">
      {/* iPad outer shell */}
      <div
        className="bg-gray-800 rounded-[40px] p-4 shadow-2xl border-2 border-gray-600 flex flex-col"
        style={{ width: 420, height: 620 }}
      >
        {/* Camera dot */}
        <div className="flex justify-center mb-1 shrink-0">
          <div className="w-2 h-2 rounded-full bg-gray-600" />
        </div>

        {/* Screen area */}
        <div className="bg-white rounded-[28px] overflow-hidden flex-1 min-h-0">
          <div className="h-full overflow-y-auto">{children}</div>
        </div>
      </div>

      {/* Home indicator bar */}
      <div className="flex justify-center mt-2">
        <div className="w-24 h-1 rounded-full bg-gray-600" />
      </div>
    </div>
  );
}
