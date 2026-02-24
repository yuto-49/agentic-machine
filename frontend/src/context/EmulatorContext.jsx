import React, { createContext, useCallback, useState } from "react";
import useProducts from "../hooks/useProducts";
import useAgentLogs from "../hooks/useAgentLogs";

export const EmulatorContext = createContext({
  products: [],
  productsLoading: true,
  wsConnected: false,
  hardwareStatus: { doorLocked: true, fridgePower: true },
  customerStep: 0,
  setCustomerStep: () => {},
  logs: [],
  logsLoading: true,
  latestAction: null,
});

/**
 * Top-level provider for the emulator page.
 * Owns shared state consumed by all three panels.
 */
export function EmulatorProvider({ children }) {
  const { products, setProducts, loading: productsLoading, wsConnected } = useProducts();

  const patchProducts = useCallback((updates) => {
    if (!Array.isArray(updates)) return;
    setProducts((prev) =>
      prev.map((p) => {
        const patch = updates.find((u) => u.product_id === p.id);
        return patch ? { ...p, quantity: patch.quantity } : p;
      })
    );
  }, [setProducts]);
  const { logs, loading: logsLoading, latestAction } = useAgentLogs();

  // Hardware status — defaults match MockHardwareController init state.
  // Future: read from a backend endpoint or WebSocket messages.
  const [hardwareStatus, setHardwareStatus] = useState({
    doorLocked: true,
    fridgePower: true,
  });

  // Customer journey step (0=Browse, 1=Select, 2=Cart, 3=Pay, 4=Done)
  const [customerStep, setCustomerStep] = useState(0);

  const handleTabChange = useCallback((tab) => {
    const mapping = { Products: 0, Cart: 2, Status: 0 };
    setCustomerStep(mapping[tab] ?? 0);
  }, []);

  return (
    <EmulatorContext.Provider
      value={{
        products,
        productsLoading,
        wsConnected,
        hardwareStatus,
        setHardwareStatus,
        customerStep,
        setCustomerStep,
        handleTabChange,
        patchProducts,
        logs,
        logsLoading,
        latestAction,
      }}
    >
      {children}
    </EmulatorContext.Provider>
  );
}
