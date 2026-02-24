import React, { useCallback, useContext } from "react";
import { EmulatorProvider, EmulatorContext } from "../../context/EmulatorContext";
import VendingMachineViz from "./VendingMachineViz";
import IPadFrame from "./IPadFrame";
import CustomerJourneyBar from "./CustomerJourneyBar";
import AgentActivityFeed from "./AgentActivityFeed";
import App from "../../App";

function EmulatorLayout() {
  const { handleTabChange, patchProducts, setCustomerStep } = useContext(EmulatorContext);

  const handleCheckoutComplete = useCallback((updatedProducts) => {
    patchProducts(updatedProducts);
    setCustomerStep(4); // Done
  }, [patchProducts, setCustomerStep]);

  return (
    <div className="grid grid-cols-emulator h-screen bg-gray-900 overflow-hidden">
      {/* Left panel — Physical Machine */}
      <div className="overflow-y-auto border-r border-gray-700">
        <VendingMachineViz />
      </div>

      {/* Center — iPad in bezel */}
      <div className="flex flex-col items-center justify-center p-6 overflow-hidden">
        <CustomerJourneyBar />
        <IPadFrame>
          <App onTabChange={handleTabChange} onCheckoutComplete={handleCheckoutComplete} />
        </IPadFrame>
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
