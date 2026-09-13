"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FolderOpen,
  Search,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  Shield,
  GitBranch,
  BarChart3,
  Trophy,
  Bell,
  Sparkles,
} from "lucide-react";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Cases", href: "/cases", icon: FolderOpen },
  { name: "Analyze", href: "/analyze", icon: Search },
  { name: "Graph", href: "/graph", icon: GitBranch },
  { name: "Risk", href: "/risk", icon: BarChart3 },
  { name: "Demo", href: "/demo", icon: Trophy },
  { name: "Reports", href: "/reports", icon: FileText },
  { name: "Settings", href: "/settings", icon: Settings },
];

const pageMeta: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": {
    title: "Investigation Command Center",
    subtitle: "Real-Time Cryptocurrency Fraud Attribution & System Health",
  },
  "/cases": {
    title: "Investigations Registry & Management",
    subtitle: "Filterable Registry of Criminal Investigations & Forensic Case Files",
  },
  "/cases/new": {
    title: "Initiate Investigation Dossier",
    subtitle: "Register New Criminal Case with Chain-of-Custody Tracking",
  },
  "/analyze": {
    title: "Single & Multi-Wallet Flow Analyzer",
    subtitle: "Multi-Hop Recursive Fund Tracking & Heuristic Engine",
  },
  "/graph": {
    title: "Interactive Investigation Graph Canvas",
    subtitle: "2D/3D Node-Link Fund Flow & Entity Cluster Visualization",
  },
  "/risk": {
    title: "Risk & VASP Attribution Engine",
    subtitle: "12-Factor Explainable ML Risk Scoring & Entity Clustering",
  },
  "/ai": {
    title: "AI Investigation Copilot",
    subtitle: "Graph-Augmented LLM Narrative & Query Assistant",
  },
  "/demo": {
    title: "Competition & Live Demo Showcase",
    subtitle: "Pre-Configured Real-World Scenarios • Smart India Hackathon SIH26183",
  },
  "/reports": {
    title: "Forensic Reports & Evidence Archive",
    subtitle: "Court-Admissible Evidence Dossiers • Section 65B Indian Evidence Act Compliant",
  },
  "/settings": {
    title: "Platform Settings & Administration",
    subtitle: "Blockchain Nodes, Database Health, User Roles & Audit Trails",
  },
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  // Determine current page header meta
  const matchedRoute = Object.keys(pageMeta).find(
    (route) => pathname === route || pathname.startsWith(route + "/")
  );
  const currentMeta = matchedRoute
    ? pageMeta[matchedRoute]
    : { title: "Forensic Intelligence Platform", subtitle: "TRACE-X Real-Time Investigation System" };

  return (
    <div className="flex h-screen bg-[#F5F7FA] text-[#151B2B] overflow-hidden">
      {/* 240px Global Left Sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-0 z-40 h-full bg-[#F8F9FC] border-r border-[#E5E7EB] transition-all duration-300 flex flex-col shadow-sm",
          collapsed ? "w-16" : "w-[240px]"
        )}
      >
        {/* Brand Header */}
        <div className="flex h-[74px] items-center justify-between px-4 border-b border-[#E5E7EB]/80 bg-white">
          {!collapsed && (
            <Link href="/dashboard" className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-[#3430D9] flex items-center justify-center shadow-sm">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-lg text-[#151B2B] tracking-tight leading-none">TRACE-X</span>
                <span className="text-[10px] text-[#73798D] font-medium tracking-wide uppercase mt-0.5">Forensics</span>
              </div>
            </Link>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded-lg hover:bg-[#F1F3F8] transition-colors text-[#73798D] hover:text-[#151B2B]"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
          </button>
        </div>

        {/* 9 Standard Navigation Items */}
        <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-150 text-sm",
                  isActive
                    ? "bg-[#EEF0FF] text-[#3430D9] font-semibold shadow-xs border-l-4 border-[#3430D9] rounded-l-none pl-2.5"
                    : "text-[#73798D] hover:bg-[#F1F3F8] hover:text-[#151B2B] font-medium",
                  collapsed && "justify-center px-0 border-l-0"
                )}
                title={collapsed ? item.name : undefined}
              >
                <item.icon
                  className={cn(
                    "w-5 h-5 flex-shrink-0 transition-colors",
                    isActive ? "text-[#3430D9]" : "text-[#73798D]"
                  )}
                  aria-hidden="true"
                />
                {!collapsed && <span className="truncate">{item.name}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Informational Sidebar Footer */}
        <div className="p-3 border-t border-[#E5E7EB]/80 bg-[#F8F9FC]">
          {!collapsed && (
            <div className="rounded-xl bg-white border border-[#E5E7EB] p-3 shadow-xs">
              <div className="flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-[#3430D9]" />
                <p className="text-xs text-[#3430D9] font-semibold tracking-tight">SIH 2026 • TRACE-X</p>
              </div>
              <p className="text-[11px] text-[#73798D] mt-1 leading-snug">
                Real-Time Cryptocurrency Fraud Attribution & Investigation Platform
              </p>
            </div>
          )}
        </div>
      </aside>

      {/* Main Layout Area: Header + Content */}
      <div
        className={cn(
          "flex-1 flex flex-col min-h-screen transition-all duration-300",
          collapsed ? "ml-16" : "ml-[240px]"
        )}
      >
        {/* 74px Global Top Header */}
        <header className="h-[74px] bg-white border-b border-[#E5E7EB] px-8 flex items-center justify-between sticky top-0 z-30 shadow-xs">
          {/* Left: Dynamic Title & Subtitle */}
          <div>
            <h1 className="text-xl font-bold text-[#151B2B] tracking-tight leading-none">{currentMeta.title}</h1>
            <p className="text-xs text-[#73798D] mt-1 font-normal">{currentMeta.subtitle}</p>
          </div>

          {/* Right: Universal Suite (Search, Settings, Alerts, Avatar) */}
          <div className="flex items-center gap-3">
            {/* Global Search Pill */}
            <div className="relative hidden md:flex items-center">
              <Search className="w-4 h-4 text-[#73798D] absolute left-3.5 pointer-events-none" />
              <input
                type="text"
                placeholder="Search cases, txns, or addresses..."
                className="w-72 h-10 pl-9 pr-4 text-xs bg-[#F1F3F8] border border-transparent rounded-full focus:outline-none focus:border-[#3430D9] focus:bg-white text-[#151B2B] transition-all"
              />
            </div>

            {/* Quick Settings Action */}
            <Link
              href="/settings"
              className="w-10 h-10 rounded-full bg-[#F1F3F8] flex items-center justify-center text-[#73798D] hover:text-[#151B2B] hover:bg-[#EEF0FF] hover:text-[#3430D9] transition-colors"
              title="Platform Settings"
            >
              <Settings className="w-4 h-4" />
            </Link>

            {/* Notification Bell with Pink/Coral Alert Dot */}
            <button
              className="relative w-10 h-10 rounded-full bg-[#F1F3F8] flex items-center justify-center text-[#73798D] hover:text-[#151B2B] hover:bg-[#EEF0FF] hover:text-[#3430D9] transition-colors"
              title="Notifications"
            >
              <Bell className="w-4 h-4" />
              <span className="absolute top-2.5 right-2.5 w-2 h-2 rounded-full bg-[#E96B98] ring-2 ring-white" />
            </button>

            {/* User Profile Avatar */}
            <div className="flex items-center gap-3 pl-2 border-l border-[#E5E7EB]">
              <div className="w-10 h-10 rounded-full bg-[#3430D9] text-white flex items-center justify-center font-semibold text-sm shadow-xs">
                RK
              </div>
              <div className="hidden lg:flex flex-col">
                <span className="text-xs font-bold text-[#151B2B] leading-none">Insp. Rajesh Kumar</span>
                <span className="text-[11px] text-[#73798D] mt-0.5 font-normal">Senior Cyber Analyst</span>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content Viewport */}
        <main className="flex-1 bg-[#F5F7FA] overflow-y-auto p-8">
          {children}
        </main>
      </div>
    </div>
  );
}