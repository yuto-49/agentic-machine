import React, { useState } from "react";
import ProductGrid from "./components/ProductGrid";
import Cart from "./components/Cart";
import MachineStatus from "./components/MachineStatus";
import IncomingTab from "./components/IncomingTab";
import PickupEntry from "./components/PickupEntry";

const TABS = ["Products", "Cart", "Pickup", "Status", "Incoming"];

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

  const totalItems = cartItems.reduce((sum, i) => sum + i.qty, 0);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Point of Sale</h1>
        <p className="text-sm text-gray-400 mt-1">
          Customer-facing POS interface
        </p>
      </div>

      {/* Tab Navigation — pill style */}
      <nav className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => {
              setActiveTab(tab);
              onTabChange?.(tab);
            }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
              activeTab === tab
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab}
            {tab === "Cart" && totalItems > 0 && (
              <span className="ml-1.5 bg-gray-900 text-white text-[10px] rounded-full px-1.5 py-0.5 font-medium">
                {totalItems}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Tab Content */}
      <div>
        {activeTab === "Products" && <ProductGrid onAddToCart={addToCart} />}
        {activeTab === "Cart" && (
          <Cart
            items={cartItems}
            onRemove={removeFromCart}
            onClear={clearCart}
            onCheckoutComplete={onCheckoutComplete}
          />
        )}
        {activeTab === "Pickup" && <PickupEntry />}
        {activeTab === "Status" && <MachineStatus />}
        {activeTab === "Incoming" && <IncomingTab />}
      </div>
    </div>
  );
}
