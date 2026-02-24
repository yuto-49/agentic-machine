import React, { useContext } from "react";
import { EmulatorContext } from "../../context/EmulatorContext";
import AgentPipelineIndicator from "./AgentPipelineIndicator";
import LogEntry from "./LogEntry";

export default function AgentActivityFeed() {
  const { logs, logsLoading, latestAction } = useContext(EmulatorContext);

  return (
    <div className="p-4 text-white h-full flex flex-col">
      <h2 className="text-lg font-bold mb-3">Agent Activity</h2>

      {/* Pipeline step indicator */}
      <AgentPipelineIndicator currentAction={latestAction} />

      {/* Log entries */}
      <div className="flex-1 overflow-y-auto mt-3 space-y-2 min-h-0">
        {logsLoading && (
          <p className="text-gray-400 text-sm">Loading logs...</p>
        )}
        {!logsLoading && logs.length === 0 && (
          <p className="text-gray-500 text-sm">
            No agent activity yet. Run{" "}
            <code className="text-gray-400">python scripts/test_agent.py</code>{" "}
            to generate activity.
          </p>
        )}
        {logs.map((log) => (
          <LogEntry key={log.id} log={log} />
        ))}
      </div>
    </div>
  );
}
