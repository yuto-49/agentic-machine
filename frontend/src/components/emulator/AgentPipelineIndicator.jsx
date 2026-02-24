import React from "react";

const PIPELINE_STEPS = [
  { key: "idle", label: "Idle" },
  { key: "received", label: "Received" },
  { key: "processing", label: "Processing" },
  { key: "tool_calls", label: "Tool Calls" },
  { key: "response", label: "Response" },
];

// Static class map — Tailwind JIT needs full class strings, no template interpolation
const ACTIVE_STYLES = {
  idle: "bg-gray-500/20 text-gray-300 ring-1 ring-gray-500",
  received: "bg-yellow-500/20 text-yellow-300 ring-1 ring-yellow-500",
  processing: "bg-blue-500/20 text-blue-300 ring-1 ring-blue-500",
  tool_calls: "bg-purple-500/20 text-purple-300 ring-1 ring-purple-500",
  response: "bg-green-500/20 text-green-300 ring-1 ring-green-500",
};

function deriveStep(action) {
  if (!action) return "idle";
  const lower = action.toLowerCase();
  if (
    lower.includes("get_inventory") ||
    lower.includes("set_price") ||
    lower.includes("unlock") ||
    lower.includes("restock") ||
    lower.includes("get_balance") ||
    lower.includes("scratchpad") ||
    lower.includes("send_message")
  )
    return "tool_calls";
  if (lower.includes("blocked")) return "processing";
  if (lower.includes("webhook") || lower.includes("receiv")) return "received";
  return "response";
}

export default function AgentPipelineIndicator({ currentAction }) {
  const activeStep = deriveStep(currentAction);

  return (
    <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
      <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-2">
        Agent Pipeline
      </p>
      <div className="flex items-center gap-1">
        {PIPELINE_STEPS.map((step, i) => (
          <React.Fragment key={step.key}>
            {i > 0 && <div className="w-3 h-0.5 bg-gray-600" />}
            <div
              className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${
                step.key === activeStep
                  ? ACTIVE_STYLES[step.key]
                  : "bg-gray-700 text-gray-500"
              }`}
            >
              {step.label}
            </div>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
