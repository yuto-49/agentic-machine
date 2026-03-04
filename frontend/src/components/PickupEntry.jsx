import React, { useState } from "react";

const KEYS = [
  ["A", "B", "C", "D", "E", "F"],
  ["G", "H", "I", "J", "K", "L"],
  ["M", "N", "O", "P", "Q", "R"],
  ["S", "T", "U", "V", "W", "X"],
  ["Y", "Z", "1", "2", "3", "4"],
  ["5", "6", "7", "8", "9", "0"],
];

export default function PickupEntry() {
  const [code, setCode] = useState("");
  const [status, setStatus] = useState(null); // null | "loading" | "success" | "error"
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleKey = (char) => {
    if (code.length < 6) {
      const newCode = code + char;
      setCode(newCode);
      if (newCode.length === 6) {
        submitCode(newCode);
      }
    }
  };

  const handleBackspace = () => {
    setCode((prev) => prev.slice(0, -1));
    setStatus(null);
    setResult(null);
    setErrorMsg("");
  };

  const handleClear = () => {
    setCode("");
    setStatus(null);
    setResult(null);
    setErrorMsg("");
  };

  const submitCode = async (pickupCode) => {
    setStatus("loading");
    setErrorMsg("");
    try {
      const resp = await fetch("/api/pickup/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: pickupCode }),
      });
      const data = await resp.json();
      if (resp.ok && data.success) {
        setStatus("success");
        setResult(data);
        setTimeout(() => {
          setCode("");
          setStatus(null);
          setResult(null);
        }, 5000);
      } else {
        setStatus("error");
        setErrorMsg(data.detail || "Invalid code");
      }
    } catch {
      setStatus("error");
      setErrorMsg("Connection error");
    }
  };

  return (
    <div className="max-w-md mx-auto">
      <h2 className="text-xl font-bold text-center mb-4">Pickup Code</h2>

      {/* Code display */}
      <div className="flex justify-center gap-2 mb-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className={`w-12 h-14 border-2 rounded-lg flex items-center justify-center text-2xl font-bold ${
              code[i]
                ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                : "border-gray-300 bg-white text-gray-400"
            }`}
          >
            {code[i] || "-"}
          </div>
        ))}
      </div>

      {/* Status messages */}
      {status === "loading" && (
        <div className="text-center text-gray-500 mb-4">Confirming...</div>
      )}
      {status === "error" && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4 text-center">
          <p className="text-red-700 font-medium">{errorMsg}</p>
          <button
            onClick={handleClear}
            className="mt-2 text-sm text-red-600 underline"
          >
            Try again
          </button>
        </div>
      )}
      {status === "success" && result && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
          <p className="text-green-700 font-bold text-center text-lg mb-2">
            Pickup Confirmed!
          </p>
          <p className="text-green-600 text-center mb-2">
            {result.customer} &mdash; ${result.total?.toFixed(2)}
          </p>
          <ul className="text-sm text-green-700 space-y-1">
            {result.items?.map((item, i) => (
              <li key={i}>
                {item.quantity}x {item.name} &mdash; ${item.subtotal?.toFixed(2)}
              </li>
            ))}
          </ul>
          <p className="text-xs text-green-500 text-center mt-3">
            Door unlocked. Auto-clearing...
          </p>
        </div>
      )}

      {/* Keypad */}
      {status !== "success" && (
        <div className="space-y-2">
          {KEYS.map((row, ri) => (
            <div key={ri} className="flex gap-2 justify-center">
              {row.map((char) => (
                <button
                  key={char}
                  onClick={() => handleKey(char)}
                  disabled={code.length >= 6 || status === "loading"}
                  className="w-12 h-12 bg-white border border-gray-300 rounded-lg text-lg font-semibold text-gray-700 active:bg-indigo-100 disabled:opacity-40"
                >
                  {char}
                </button>
              ))}
            </div>
          ))}
          <div className="flex gap-2 justify-center mt-2">
            <button
              onClick={handleBackspace}
              disabled={code.length === 0 || status === "loading"}
              className="flex-1 max-w-[8rem] h-12 bg-gray-200 rounded-lg font-medium text-gray-700 active:bg-gray-300 disabled:opacity-40"
            >
              Back
            </button>
            <button
              onClick={handleClear}
              disabled={code.length === 0 || status === "loading"}
              className="flex-1 max-w-[8rem] h-12 bg-red-100 rounded-lg font-medium text-red-600 active:bg-red-200 disabled:opacity-40"
            >
              Clear
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
