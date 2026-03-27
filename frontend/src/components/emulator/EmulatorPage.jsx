import React, { useCallback, useContext, useState } from "react";
import { EmulatorProvider, EmulatorContext } from "../../context/EmulatorContext";
import VendingMachineViz from "./VendingMachineViz";
import AgentActivityFeed from "./AgentActivityFeed";
import App from "../../App";
import AdminDashboard from "../AdminDashboard";
import ScenarioRunner from "../ScenarioRunner";
import TestMonitorTab from "../TestMonitorTab";
import DashboardHome from "../DashboardHome";

/* ── Inline SVG icons (Heroicons-style, keeps us dependency-free) ── */

function Icon({ name, className = "w-5 h-5" }) {
  const shared = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    className,
  };

  switch (name) {
    case "dashboard":
      return (
        <svg {...shared}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "pos":
      return (
        <svg {...shared}>
          <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z" />
          <path d="M3 6h18" />
          <path d="M16 10a4 4 0 01-8 0" />
        </svg>
      );
    case "admin":
      return (
        <svg {...shared}>
          <path d="M18 20V10M12 20V4M6 20v-6" />
        </svg>
      );
    case "simulate":
      return (
        <svg {...shared}>
          <circle cx="12" cy="12" r="10" />
          <polygon
            points="10,8 16,12 10,16"
            fill="currentColor"
            stroke="none"
          />
        </svg>
      );
    case "testlab":
      return (
        <svg {...shared}>
          <path d="M9 3h6M10 3v5.2a2 2 0 01-.6 1.4L5.6 13.4A4 4 0 004 16.2V18a2 2 0 002 2h12a2 2 0 002-2v-1.8a4 4 0 00-1.2-2.8L15 9.6A2 2 0 0114 8.2V3" />
        </svg>
      );
    case "machine":
      return (
        <svg {...shared}>
          <rect x="2" y="2" width="20" height="8" rx="2" />
          <rect x="2" y="14" width="20" height="8" rx="2" />
          <circle cx="6" cy="6" r="1" fill="currentColor" stroke="none" />
          <circle cx="6" cy="18" r="1" fill="currentColor" stroke="none" />
        </svg>
      );
    default:
      return null;
  }
}

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard" },
  { id: "pos", label: "Point of Sale", icon: "pos" },
  { id: "admin", label: "Admin", icon: "admin" },
  { id: "simulate", label: "Simulate", icon: "simulate" },
  { id: "testlab", label: "Test Lab", icon: "testlab" },
  { id: "machine", label: "Machine", icon: "machine" },
];

function EmulatorLayout() {
  const [activePage, setActivePage] = useState("dashboard");
  const { handleTabChange, patchProducts, setCustomerStep, wsConnected } =
    useContext(EmulatorContext);

  const handleCheckoutComplete = useCallback(
    (updatedProducts) => {
      patchProducts(updatedProducts);
      setCustomerStep(4);
    },
    [patchProducts, setCustomerStep]
  );

  return (
    <div className="flex h-screen bg-[#f5f5f7]">
      {/* ── Sidebar ── */}
      <aside className="w-60 bg-white/80 backdrop-blur-xl border-r border-gray-200/60 flex flex-col shrink-0">
        {/* Branding */}
        <div className="px-6 pt-8 pb-6">
          <h1 className="text-xl font-semibold tracking-tight text-gray-900">
            Claudius
          </h1>
          <p className="text-[11px] text-gray-400 mt-1">AI Vending Machine</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 space-y-1">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setActivePage(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13px] transition-all duration-150 ${
                activePage === item.id
                  ? "bg-gray-900 text-white font-medium shadow-sm"
                  : "text-gray-500 hover:bg-gray-100 hover:text-gray-700"
              }`}
            >
              <Icon name={item.icon} className="w-[18px] h-[18px] shrink-0" />
              {item.label}
            </button>
          ))}
        </nav>

        {/* Connection status */}
        <div className="px-6 py-5 border-t border-gray-200/60">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                wsConnected ? "bg-green-400" : "bg-gray-300"
              }`}
            />
            <span className="text-[11px] text-gray-400">
              {wsConnected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-10 py-8">
          {activePage === "dashboard" && <DashboardHome />}

          {activePage === "pos" && (
            <App
              onTabChange={handleTabChange}
              onCheckoutComplete={handleCheckoutComplete}
            />
          )}

          {activePage === "admin" && <AdminDashboard />}

          {activePage === "simulate" && <ScenarioRunner />}

          {activePage === "testlab" && <TestMonitorTab />}

          {activePage === "machine" && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-semibold text-gray-900">
                  Machine
                </h1>
                <p className="text-sm text-gray-400 mt-1">
                  Physical machine visualization and agent activity
                </p>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-900 rounded-2xl min-h-[520px]">
                  <VendingMachineViz />
                </div>
                <div className="bg-gray-900 rounded-2xl min-h-[520px]">
                  <AgentActivityFeed />
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
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
