import React, { useCallback, useContext } from "react";
import { EmulatorProvider, EmulatorContext } from "../../context/EmulatorContext";
import VendingMachineViz from "./VendingMachineViz";
import IPadFrame from "./IPadFrame";
import CustomerJourneyBar from "./CustomerJourneyBar";
import AgentActivityFeed from "./AgentActivityFeed";
import MonitorFrame from "./MonitorFrame";
import App from "../../App";
import AdminDashboard from "../AdminDashboard";

function EmulatorLayout() {
  const { handleTabChange, patchProducts, setCustomerStep } = useContext(EmulatorContext);

  const handleCheckoutComplete = useCallback((updatedProducts) => {
    patchProducts(updatedProducts);
    setCustomerStep(4); // Done
  }, [patchProducts, setCustomerStep]);

  return (
    <div
      className="grid h-screen bg-gray-900 overflow-hidden"
      style={{ gridTemplateColumns: "320px 1fr 1fr 240px" }}
    >
      {/* Left panel — Physical Machine */}
      <div className="overflow-y-auto border-r border-gray-700">
        <VendingMachineViz />
      </div>

      {/* Center-left — iPad in bezel */}
      <div className="flex flex-col items-center justify-center p-3 overflow-hidden min-w-0">
        <CustomerJourneyBar />
        <IPadFrame>
          <App onTabChange={handleTabChange} onCheckoutComplete={handleCheckoutComplete} />
        </IPadFrame>
      </div>

      {/* Center-right — Admin Panel in monitor frame */}
      <div className="flex flex-col items-center justify-center p-3 overflow-hidden min-w-0">
        <MonitorFrame>
          <AdminDashboard />
        </MonitorFrame>
      </div>

      {/* Right panel — Agent Activity */}
      <div className="overflow-y-auto border-l border-gray-700">
        <AgentActivityFeed />
      </div>
    </div>
  );
}

export default function EmulatorPage() {
  return (
    <EmulatorProvider>
      <EmulatorLayout />
    </EmulatorProvider>
  );
}
