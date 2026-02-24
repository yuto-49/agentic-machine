import React, { useState } from "react";

export default function Cart({ items, onRemove, onClear, onCheckoutComplete }) {
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState(null);

  const total = items.reduce((sum, i) => sum + i.sell_price * i.qty, 0);

  const handleCheckout = async () => {
    setChecking(true);
    setResult(null);
    try {
      const res = await fetch("/api/cart/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: items.map((i) => ({ product_id: i.id, quantity: i.qty })),
          payment_method: "honor_system",
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setResult({ success: true, message: data.message });
        onCheckoutComplete?.(data.updated_products);
        onClear();
      } else {
        setResult({ success: false, message: data.detail || "Checkout failed" });
      }
    } catch (err) {
      setResult({ success: false, message: err.message });
    } finally {
      setChecking(false);
    }
  };

  if (items.length === 0 && !result) {
    return <p className="text-center py-8 text-gray-500">Your cart is empty.</p>;
  }

  return (
    <div>
      {result && (
        <div
          className={`p-4 rounded mb-4 ${
            result.success ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
          }`}
        >
          {result.message}
        </div>
      )}

      {items.length > 0 && (
        <>
          <div className="bg-white rounded-lg shadow divide-y">
            {items.map((item) => (
              <div key={item.id} className="flex items-center justify-between p-4">
                <div>
                  <p className="font-medium">{item.name}</p>
                  <p className="text-sm text-gray-500">
                    ${item.sell_price.toFixed(2)} x {item.qty}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-semibold">
                    ${(item.sell_price * item.qty).toFixed(2)}
                  </span>
                  <button
                    onClick={() => onRemove(item.id)}
                    className="text-red-500 text-sm hover:underline"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 flex items-center justify-between">
            <span className="text-xl font-bold">Total: ${total.toFixed(2)}</span>
            <button
              onClick={handleCheckout}
              disabled={checking}
              className="bg-indigo-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-indigo-700 disabled:bg-gray-400"
            >
              {checking ? "Processing..." : "Checkout"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
