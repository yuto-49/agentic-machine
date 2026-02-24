import React, { useContext } from "react";
import { EmulatorContext } from "../../context/EmulatorContext";

const STEPS = ["Browse", "Select", "Cart", "Pay", "Done"];

export default function CustomerJourneyBar() {
  const { customerStep } = useContext(EmulatorContext);

  return (
    <div className="flex items-center gap-2 mb-4 text-xs">
      {STEPS.map((step, i) => (
        <React.Fragment key={step}>
          {i > 0 && (
            <div
              className={`w-6 h-0.5 ${i <= customerStep ? "bg-indigo-400" : "bg-gray-600"}`}
            />
          )}
          <div
            className={`flex items-center gap-1 px-2 py-1 rounded-full ${
              i === customerStep
                ? "bg-indigo-500 text-white"
                : i < customerStep
                  ? "bg-indigo-900 text-indigo-300"
                  : "bg-gray-700 text-gray-400"
            }`}
          >
            <span className="w-4 h-4 rounded-full border border-current flex items-center justify-center text-[10px]">
              {i < customerStep ? "\u2713" : i + 1}
            </span>
            {step}
          </div>
        </React.Fragment>
      ))}
    </div>
  );
}
