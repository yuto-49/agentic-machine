import React, { useState } from "react";
import {
  useScenarioPresets,
  useScenarioRun,
  useScenarioHistory,
} from "../hooks/useScenario";

function ScoreBar({ score }) {
  const color =
    score >= 70 ? "bg-green-500" : score >= 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="w-full bg-gray-200 rounded-full h-4">
      <div
        className={`${color} h-4 rounded-full transition-all`}
        style={{ width: `${score}%` }}
      />
    </div>
  );
}

function TranscriptPanel({ transcript }) {
  if (!transcript || transcript.length === 0) return null;

  return (
    <div className="space-y-3 max-h-96 overflow-y-auto">
      {transcript.map((turn, i) => {
        const isCustomer = turn.role === "customer";
        return (
          <div
            key={i}
            className={`flex ${isCustomer ? "justify-start" : "justify-end"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                isCustomer
                  ? "bg-gray-100 text-gray-800"
                  : "bg-indigo-100 text-indigo-900"
              }`}
            >
              <div className="text-xs font-semibold mb-1 opacity-60">
                {isCustomer ? "Customer" : "Seller (Claudius)"} — Turn{" "}
                {turn.turn_number}
              </div>
              <div className="text-sm whitespace-pre-wrap">
                {turn.message
                  .replace(/\[DEAL_CLOSED[^\]]*\]/gi, "")
                  .replace(/\[ACCEPT_DEAL\]/gi, "")
                  .replace(/\[WALK_AWAY\]/gi, "")
                  .replace(/\[CUSTOMER_LEFT\]/gi, "")
                  .replace(/\[ESCALAT[A-Z]*\]/gi, "")
                  .trim()}
              </div>
              {turn.guardrail_hit && (
                <div className="mt-1 text-xs text-red-600 font-medium">
                  Guardrail: {turn.guardrail_detail}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function OutcomePanel({ outcome, spec }) {
  if (!outcome) return null;

  const dealColor = outcome.deal_closed ? "text-green-700" : "text-red-700";
  const dealBg = outcome.deal_closed ? "bg-green-50" : "bg-red-50";

  return (
    <div className="space-y-4">
      {/* Result badge */}
      <div className={`${dealBg} rounded-lg p-4 text-center`}>
        <div className={`text-2xl font-bold ${dealColor}`}>
          {outcome.deal_closed ? "Deal Closed" : "No Deal"}
        </div>
        <div className="text-sm text-gray-600 mt-1">
          {outcome.customer_sentiment} customer
        </div>
      </div>

      {/* Price path */}
      {outcome.deal_closed && outcome.final_price && (
        <div className="bg-white rounded-lg border p-3">
          <div className="text-xs text-gray-500 uppercase font-medium">
            Price Path
          </div>
          <div className="flex items-center justify-between mt-2">
            <div>
              <div className="text-xs text-gray-400">List</div>
              <div className="font-medium">
                ${spec?.sell_price?.toFixed(2) || "—"}
              </div>
            </div>
            <div className="text-gray-300">→</div>
            <div>
              <div className="text-xs text-gray-400">Final</div>
              <div className="font-bold text-lg">
                ${outcome.final_price.toFixed(2)}
              </div>
            </div>
            <div className="text-gray-300">→</div>
            <div>
              <div className="text-xs text-gray-400">Margin</div>
              <div
                className={`font-medium ${
                  outcome.margin_achieved >= 0.3
                    ? "text-green-600"
                    : "text-red-600"
                }`}
              >
                {outcome.margin_achieved
                  ? `${(outcome.margin_achieved * 100).toFixed(0)}%`
                  : "—"}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Seller score */}
      <div className="bg-white rounded-lg border p-3">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-gray-500 uppercase font-medium">
            Seller Score
          </span>
          <span className="font-bold text-lg">{outcome.seller_score}/100</span>
        </div>
        <ScoreBar score={outcome.seller_score} />
      </div>

      {/* Tactics used */}
      {outcome.tactics_used && outcome.tactics_used.length > 0 && (
        <div className="bg-white rounded-lg border p-3">
          <div className="text-xs text-gray-500 uppercase font-medium mb-2">
            Tactics Used
          </div>
          <div className="flex flex-wrap gap-1">
            {outcome.tactics_used.map((t, i) => (
              <span
                key={i}
                className="bg-indigo-50 text-indigo-700 text-xs px-2 py-1 rounded"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Guardrail hits */}
      {outcome.guardrail_hits > 0 && (
        <div className="bg-red-50 rounded-lg border border-red-200 p-3">
          <div className="text-xs text-red-500 uppercase font-medium">
            Guardrail Violations
          </div>
          <div className="text-red-700 font-bold text-lg">
            {outcome.guardrail_hits}
          </div>
        </div>
      )}

      {/* Training signal */}
      {outcome.training_signal && (
        <div className="bg-amber-50 rounded-lg border border-amber-200 p-3">
          <div className="text-xs text-amber-600 uppercase font-medium mb-1">
            Training Signal
          </div>
          <div className="text-sm text-amber-800">
            {outcome.training_signal}
          </div>
        </div>
      )}

      {/* Summary */}
      {outcome.summary && (
        <div className="text-sm text-gray-600 italic">{outcome.summary}</div>
      )}
    </div>
  );
}

export default function ScenarioRunner() {
  const { presets, loading: presetsLoading } = useScenarioPresets();
  const { run, result, running, error } = useScenarioRun();
  const { scenarios: history, refresh: refreshHistory } = useScenarioHistory();

  const [prompt, setPrompt] = useState("");
  const [selectedPreset, setSelectedPreset] = useState(null);
  const [showHistory, setShowHistory] = useState(false);

  const handleRun = async () => {
    const text = selectedPreset
      ? presets.find((p) => p.id === selectedPreset)?.prompt || prompt
      : prompt;

    if (!text || text.length < 10) return;

    await run(text, selectedPreset);
    refreshHistory();
  };

  const handlePresetSelect = (presetId) => {
    const preset = presets.find((p) => p.id === presetId);
    if (preset) {
      setSelectedPreset(presetId);
      setPrompt(preset.prompt);
    }
  };

  return (
    <div className="space-y-6">
      {/* Input section */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-semibold mb-3">Scenario Simulator</h2>
        <p className="text-sm text-gray-500 mb-4">
          Simulate customer-seller interactions to train the agent's negotiation
          skills. The seller always protects profit.
        </p>

        {/* Preset selector */}
        <div className="mb-3">
          <label className="text-xs text-gray-500 uppercase font-medium">
            Preset Scenarios
          </label>
          <div className="flex flex-wrap gap-2 mt-1">
            <button
              onClick={() => {
                setSelectedPreset(null);
                setPrompt("");
              }}
              className={`text-xs px-3 py-1.5 rounded-full border ${
                !selectedPreset
                  ? "bg-indigo-600 text-white border-indigo-600"
                  : "bg-white text-gray-600 border-gray-300 hover:border-indigo-300"
              }`}
            >
              Custom
            </button>
            {presets.map((p) => (
              <button
                key={p.id}
                onClick={() => handlePresetSelect(p.id)}
                title={p.description}
                className={`text-xs px-3 py-1.5 rounded-full border ${
                  selectedPreset === p.id
                    ? "bg-indigo-600 text-white border-indigo-600"
                    : "bg-white text-gray-600 border-gray-300 hover:border-indigo-300"
                }`}
              >
                {p.title}
              </button>
            ))}
          </div>
        </div>

        {/* Prompt input */}
        <textarea
          value={prompt}
          onChange={(e) => {
            setPrompt(e.target.value);
            setSelectedPreset(null);
          }}
          placeholder="Describe a scenario... e.g. 'A student wants to buy a Coca-Cola but tries to negotiate the price down because they think it's overpriced'"
          className="w-full border rounded-lg p-3 text-sm h-24 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300"
          disabled={running}
        />

        {/* Run button */}
        <div className="flex items-center justify-between mt-3">
          <button
            onClick={handleRun}
            disabled={running || (!prompt && !selectedPreset)}
            className={`px-6 py-2 rounded-lg font-medium text-sm ${
              running || (!prompt && !selectedPreset)
                ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                : "bg-indigo-600 text-white hover:bg-indigo-700"
            }`}
          >
            {running ? "Simulating..." : "Run Simulation"}
          </button>

          <button
            onClick={() => setShowHistory(!showHistory)}
            className="text-sm text-gray-500 hover:text-indigo-600"
          >
            {showHistory ? "Hide" : "Show"} History ({history.length})
          </button>
        </div>

        {error && (
          <div className="mt-3 text-sm text-red-600 bg-red-50 rounded p-2">
            {error}
          </div>
        )}
      </div>

      {/* Loading indicator */}
      {running && (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="animate-spin h-8 w-8 border-4 border-indigo-600 border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-gray-600 text-sm">
            Running simulation... This takes 15-60 seconds.
          </p>
          <p className="text-gray-400 text-xs mt-1">
            Parsing scenario, running dialogue turns, evaluating outcome.
          </p>
        </div>
      )}

      {/* Results */}
      {result && !running && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Transcript (2/3 width on large screens) */}
          <div className="lg:col-span-2 bg-white rounded-lg shadow p-4">
            <h3 className="text-sm font-semibold text-gray-700 uppercase mb-3">
              Transcript — {result.spec?.title || "Simulation"}
            </h3>
            <TranscriptPanel transcript={result.transcript} />
          </div>

          {/* Outcome panel (1/3 width) */}
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-sm font-semibold text-gray-700 uppercase mb-3">
              Outcome
            </h3>
            <OutcomePanel outcome={result.outcome} spec={result.spec} />
          </div>
        </div>
      )}

      {/* History */}
      {showHistory && history.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-gray-700 uppercase mb-3">
            Past Simulations
          </h3>
          <div className="space-y-2">
            {history.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between border rounded p-2 text-sm"
              >
                <div className="flex-1">
                  <span className="text-gray-800">{s.prompt}</span>
                </div>
                <div className="flex items-center gap-3 ml-4">
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded ${
                      s.outcome === "deal_closed"
                        ? "bg-green-100 text-green-700"
                        : s.status === "failed"
                        ? "bg-red-100 text-red-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {s.outcome || s.status}
                  </span>
                  {s.seller_score !== null && (
                    <span className="text-xs text-gray-500">
                      Score: {s.seller_score}
                    </span>
                  )}
                  <span className="text-xs text-gray-400">
                    {s.total_turns} turns
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
