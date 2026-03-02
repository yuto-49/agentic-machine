import React, { useState } from "react";
import ProductGrid from "./components/ProductGrid";
import Cart from "./components/Cart";
import MachineStatus from "./components/MachineStatus";
import IncomingTab from "./components/IncomingTab";

const TABS = ["Products", "Cart", "Status", "Incoming"];

export default function App({ onTabChange, onCheckoutComplete }) {
  const [activeTab, setActiveTab] = useState("Products");
  const [cartItems, setCartItems] = useState([]);

  const addToCart = (product) => {
    setCartItems((prev) => {
      const existing = prev.find((i) => i.id === product.id);
      if (existing) {
        return prev.map((i) =>
          i.id === product.id ? { ...i, qty: i.qty + 1 } : i
        );
      }
      return [...prev, { ...product, qty: 1 }];
    });
  };

  const removeFromCart = (productId) => {
    setCartItems((prev) => prev.filter((i) => i.id !== productId));
  };

  const clearCart = () => setCartItems([]);

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-indigo-600 text-white p-4 text-center">
        <h1 className="text-2xl font-bold">Claudius</h1>
        <p className="text-sm opacity-80">AI Vending Machine</p>
      </header>

      {/* Tab Navigation */}
      <nav className="flex border-b bg-white">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); onTabChange?.(tab); }}
            className={`flex-1 py-3 text-center font-medium ${
              activeTab === tab
                ? "text-indigo-600 border-b-2 border-indigo-600"
                : "text-gray-500"
            }`}
          >
            {tab}
            {tab === "Cart" && cartItems.length > 0 && (
              <span className="ml-1 bg-indigo-600 text-white text-xs rounded-full px-2 py-0.5">
                {cartItems.reduce((sum, i) => sum + i.qty, 0)}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Tab Content */}
      <main className="p-4 max-w-4xl mx-auto">
        {activeTab === "Products" && <ProductGrid onAddToCart={addToCart} />}
        {activeTab === "Cart" && (
          <Cart
            items={cartItems}
            onRemove={removeFromCart}
            onClear={clearCart}
            onCheckoutComplete={onCheckoutComplete}
          />
        )}
        {activeTab === "Status" && <MachineStatus />}
        {activeTab === "Incoming" && <IncomingTab />}
      </main>
    </div>
  );
}
