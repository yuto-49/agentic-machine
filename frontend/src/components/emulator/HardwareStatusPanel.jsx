import React from "react";

function StatusIndicator({
  label,
  active,
  activeColor,
  inactiveColor,
  activeText,
  inactiveText,
}) {
  return (
    <div className="bg-gray-800 rounded p-2 border border-gray-700 flex items-center gap-2">
      <div
        className={`w-2.5 h-2.5 rounded-full ${active ? activeColor : inactiveColor}`}
      />
      <div>
        <p className="text-[10px] text-gray-400">{label}</p>
        <p className="text-xs font-medium text-gray-200">
          {active ? activeText : inactiveText}
        </p>
      </div>
    </div>
  );
}

export default function HardwareStatusPanel({ status }) {
  return (
    <div className="mt-4 space-y-2">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
        Hardware
      </h3>
      <div className="grid grid-cols-2 gap-2">
        <StatusIndicator
          label="Door Lock"
          active={status.doorLocked}
          activeColor="bg-green-500"
          inactiveColor="bg-red-500"
          activeText="Locked"
          inactiveText="Unlocked"
        />
        <StatusIndicator
          label="Fridge"
          active={status.fridgePower}
          activeColor="bg-blue-500"
          inactiveColor="bg-gray-500"
          activeText="ON"
          inactiveText="OFF"
        />
      </div>
    </div>
  );
}
