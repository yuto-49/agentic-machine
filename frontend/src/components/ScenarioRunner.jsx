import React, { useState, useEffect, useRef } from "react";
import {
  useScenarioPresets,
  useScenarioRun,
  useScenarioHistory,
} from "../hooks/useScenario";

function ScoreBar({ score }) {
  const color =
    score >= 70 ? "bg-green-500" : score >= 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="w-full bg-gray-100 rounded-full h-3">
      <div
        className={`${color} h-3 rounded-full transition-all duration-500`}
        style={{ width: `${score}%` }}
      />
    </div>
  );
}

function TranscriptPanel({ transcript }) {
  if (!transcript || transcript.length === 0) return null;

  return (
    <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
      {transcript.map((turn, i) => {
        const isCustomer = turn.role === "customer";
        return (
          <div
            key={i}
            className={`flex ${isCustomer ? "justify-start" : "justify-end"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-5 py-3 ${
                isCustomer
                  ? "bg-gray-100 text-gray-800"
                  : "bg-gray-900 text-white"
              }`}
            >
              <div
                className={`text-[10px] font-medium mb-1.5 ${
                  isCustomer ? "text-gray-400" : "text-gray-400"
                }`}
              >
                {isCustomer ? "Customer" : "Seller (Claudius)"} &middot; Turn{" "}
                {turn.turn_number}
              </div>
              <div className="text-sm leading-relaxed whitespace-pre-wrap">
                {turn.message
                  .replace(/\[DEAL_CLOSED[^\]]*\]/gi, "")
                  .replace(/\[ACCEPT_DEAL\]/gi, "")
                  .replace(/\[WALK_AWAY\]/gi, "")
                  .replace(/\[CUSTOMER_LEFT\]/gi, "")
                  .replace(/\[ESCALAT[A-Z]*\]/gi, "")
                  .trim()}
              </div>
              {turn.guardrail_hit && (
                <div className="mt-2 text-xs text-red-400 font-medium">
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

  const dealColor = outcome.deal_closed ? "text-green-600" : "text-red-600";
  const dealBg = outcome.deal_closed ? "bg-green-50" : "bg-red-50";

  return (
    <div className="space-y-5">
      {/* Result badge */}
      <div className={`${dealBg} rounded-2xl p-6 text-center`}>
        <div className={`text-2xl font-bold ${dealColor}`}>
          {outcome.deal_closed ? "Deal Closed" : "No Deal"}
        </div>
        <div className="text-sm text-gray-500 mt-1 capitalize">
          {outcome.customer_sentiment} customer
        </div>
      </div>

      {/* Price path */}
      {outcome.deal_closed && outcome.final_price && (
        <div className="bg-white rounded-2xl border border-gray-200/60 p-5">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-4">
            Price Path
          </p>
          <div className="flex items-center justify-between">
            <div className="text-center">
              <div className="text-xs text-gray-400">List</div>
              <div className="font-medium text-gray-800 mt-1">
                ${spec?.sell_price?.toFixed(2) || "\u2014"}
              </div>
            </div>
            <div className="text-gray-300 text-lg">&rarr;</div>
            <div className="text-center">
              <div className="text-xs text-gray-400">Final</div>
              <div className="font-bold text-xl text-gray-900 mt-1">
                ${outcome.final_price.toFixed(2)}
              </div>
            </div>
            <div className="text-gray-300 text-lg">&rarr;</div>
            <div className="text-center">
              <div className="text-xs text-gray-400">Margin</div>
              <div
                className={`font-medium mt-1 ${
                  outcome.margin_achieved >= 0.3
                    ? "text-green-600"
                    : "text-red-600"
                }`}
              >
                {outcome.margin_achieved
                  ? `${(outcome.margin_achieved * 100).toFixed(0)}%`
                  : "\u2014"}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Seller score */}
      <div className="bg-white rounded-2xl border border-gray-200/60 p-5">
        <div className="flex justify-between items-center mb-3">
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            Seller Score
          </span>
          <span className="font-bold text-xl">{outcome.seller_score}/100</span>
        </div>
        <ScoreBar score={outcome.seller_score} />
      </div>

      {/* Tactics used */}
      {outcome.tactics_used && outcome.tactics_used.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200/60 p-5">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
            Tactics Used
          </p>
          <div className="flex flex-wrap gap-2">
            {outcome.tactics_used.map((t, i) => (
              <span
                key={i}
                className="bg-gray-100 text-gray-700 text-xs px-3 py-1.5 rounded-lg"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Guardrail hits */}
      {outcome.guardrail_hits > 0 && (
        <div className="bg-red-50 rounded-2xl border border-red-200 p-5">
          <p className="text-xs text-red-500 uppercase font-medium tracking-wider">
            Guardrail Violations
          </p>
          <p className="text-red-700 font-bold text-xl mt-2">
            {outcome.guardrail_hits}
          </p>
        </div>
      )}

      {/* Training signal */}
      {outcome.training_signal && (
        <div className="bg-amber-50 rounded-2xl border border-amber-200 p-5">
          <p className="text-xs text-amber-600 uppercase font-medium tracking-wider mb-2">
            Training Signal
          </p>
          <p className="text-sm text-amber-800 leading-relaxed">
            {outcome.training_signal}
          </p>
        </div>
      )}

      {/* Summary */}
      {outcome.summary && (
        <p className="text-sm text-gray-500 leading-relaxed italic px-1">
          {outcome.summary}
        </p>
      )}
    </div>
  );
}

const ERROR_CONFIG = {
  billing: {
    title: "API Credits Exhausted",
    message:
      "Please check your Anthropic billing and add credits to run simulations.",
    bg: "bg-amber-50",
    border: "border-amber-200",
    text: "text-amber-800",
  },
  rate_limit: {
    title: "Rate Limited",
    message:
      "The API is temporarily rate limited. Please wait a moment and try again.",
    bg: "bg-blue-50",
    border: "border-blue-200",
    text: "text-blue-800",
  },
  config: {
    title: "Configuration Error",
    message: "API key is not configured. Set ANTHROPIC_API_KEY in your .env file.",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    text: "text-yellow-800",
  },
  api_error: {
    title: "AI Service Unavailable",
    message: "The AI service is temporarily unavailable. Please try again later.",
    bg: "bg-gray-50",
    border: "border-gray-200",
    text: "text-gray-800",
  },
};

function ErrorBanner({ error, errorType, onRetry }) {
  const config = ERROR_CONFIG[errorType];

  if (config) {
    return (
      <div
        className={`mt-4 rounded-2xl border ${config.bg} ${config.border} p-5`}
      >
        <p className={`font-semibold text-sm ${config.text}`}>{config.title}</p>
        <p className={`text-sm ${config.text} opacity-80 mt-1`}>
          {config.message}
        </p>
        {errorType === "rate_limit" && onRetry && (
          <button
            onClick={onRetry}
            className="mt-3 text-xs px-4 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="mt-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-2xl p-5">
      {error}
    </div>
  );
}

export default function ScenarioRunner() {
  const { presets, loading: presetsLoading } = useScenarioPresets();
  const { run, result, running, error, errorType } = useScenarioRun();
  const { scenarios: history, refresh: refreshHistory } = useScenarioHistory();

  const [prompt, setPrompt] = useState("");
  const [selectedPreset, setSelectedPreset] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (running) {
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    } else {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => clearInterval(timerRef.current);
  }, [running]);

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
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Simulate</h1>
        <p className="text-sm text-gray-400 mt-1">
          Run customer-seller negotiations to train the agent's skills
        </p>
      </div>

      {/* Input section */}
      <div className="bg-white rounded-2xl border border-gray-200/60 p-8">
        {/* Preset selector */}
        <div className="mb-5">
          <label className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            Preset Scenarios
          </label>
          <div className="flex flex-wrap gap-2 mt-3">
            <button
              onClick={() => {
                setSelectedPreset(null);
                setPrompt("");
              }}
              disabled={running}
              className={`text-xs px-4 py-2 rounded-lg border transition-colors ${
                running
                  ? "bg-gray-100 text-gray-300 border-gray-100 cursor-not-allowed"
                  : !selectedPreset
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-300"
              }`}
            >
              Custom
            </button>
            {presets.map((p) => (
              <button
                key={p.id}
                onClick={() => handlePresetSelect(p.id)}
                disabled={running}
                title={p.description}
                className={`text-xs px-4 py-2 rounded-lg border transition-colors ${
                  running
                    ? "bg-gray-100 text-gray-300 border-gray-100 cursor-not-allowed"
                    : selectedPreset === p.id
                    ? "bg-gray-900 text-white border-gray-900"
                    : "bg-white text-gray-600 border-gray-200 hover:border-gray-300"
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
          className="w-full border border-gray-200 rounded-xl p-4 text-sm h-28 resize-none focus:outline-none focus:ring-2 focus:ring-gray-900/10 bg-gray-50"
          disabled={running}
        />

        {/* Actions */}
        <div className="flex items-center justify-between mt-4">
          <button
            onClick={handleRun}
            disabled={running || (!prompt && !selectedPreset)}
            className={`px-6 py-2.5 rounded-xl font-medium text-sm transition-all ${
              running || (!prompt && !selectedPreset)
                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                : "bg-gray-900 text-white hover:bg-gray-800 shadow-sm"
            }`}
          >
            {running ? "Simulating..." : "Run Simulation"}
          </button>

          <button
            onClick={() => setShowHistory(!showHistory)}
            className="text-sm text-gray-400 hover:text-gray-600 transition-colors"
          >
            {showHistory ? "Hide" : "Show"} History ({history.length})
          </button>
        </div>

        {error && (
          <ErrorBanner error={error} errorType={errorType} onRetry={handleRun} />
        )}
      </div>

      {/* Loading indicator */}
      {running && (
        <div className="bg-white rounded-2xl border border-gray-200/60 p-10 text-center">
          <div className="animate-spin h-8 w-8 border-[3px] border-gray-900 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-gray-600 text-sm">{elapsed}s elapsed</p>
          <p className="text-gray-400 text-xs mt-1">
            Parsing scenario, running dialogue turns, evaluating outcome
          </p>
          {elapsed >= 60 && (
            <p className="text-amber-600 text-xs mt-3">
              Taking longer than expected... still working.
            </p>
          )}
        </div>
      )}

      {/* Results */}
      {result && !running && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Transcript (3/5 width) */}
          <div className="lg:col-span-3 bg-white rounded-2xl border border-gray-200/60 p-6">
            <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-5">
              Transcript &mdash; {result.spec?.title || "Simulation"}
            </h3>
            <TranscriptPanel transcript={result.transcript} />
          </div>

          {/* Outcome panel (2/5 width) */}
          <div className="lg:col-span-2">
            <div className="sticky top-8">
              <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-5">
                Outcome
              </h3>
              <OutcomePanel outcome={result.outcome} spec={result.spec} />
            </div>
          </div>
        </div>
      )}

      {/* History */}
      {showHistory && history.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200/60 p-8">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-5">
            Past Simulations
          </h3>
          <div className="space-y-3">
            {history.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between rounded-xl bg-gray-50 p-4"
              >
                <div className="flex-1 min-w-0">
                  <span className="text-sm text-gray-800">{s.prompt}</span>
                </div>
                <div className="flex items-center gap-4 ml-6 shrink-0">
                  <span
                    className={`text-xs font-medium px-2.5 py-1 rounded-full ${
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
                    <span className="text-xs text-gray-400">
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
