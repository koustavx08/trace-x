"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
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
  Fingerprint,
  Trophy,
  Bell,
  Sparkles,
  Sun,
  Moon,
  LogOut,
} from "lucide-react";
import { useLandingTheme } from "@/lib/theme-context";
import { useAuthStore } from "@/store/auth-store";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Cases", href: "/cases", icon: FolderOpen },
  { name: "Analyze", href: "/analyze", icon: Search },
  { name: "Graph", href: "/graph", icon: GitBranch },
  { name: "Risk", href: "/risk", icon: BarChart3 },
  { name: "Forensics", href: "/forensics", icon: Fingerprint },
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
  const router = useRouter();
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);
  const { theme, toggleTheme } = useLandingTheme();
  const isLight = theme === "light";

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  // Determine current page header meta
  const matchedRoute = Object.keys(pageMeta).find(
    (route) => pathname === route || pathname.startsWith(route + "/")
  );
  const currentMeta = matchedRoute
    ? pageMeta[matchedRoute]
    : { title: "Forensic Intelligence Platform", subtitle: "TRACE-X Real-Time Investigation System" };

  return (
    <div
      className={`flex h-screen overflow-hidden font-mono transition-colors duration-300 ${
        isLight
          ? "bg-slate-100 text-slate-900"
          : "bg-[#090909] text-white selection:bg-[#cf0] selection:text-black"
      }`}
    >
      {/* 240px Global Left Sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-0 z-40 h-full border-r transition-all duration-300 flex flex-col shadow-lg justify-between",
          isLight
            ? "bg-white border-slate-200"
            : "bg-[#0d0d0d] border-[#222]",
          collapsed ? "w-16" : "w-[240px]"
        )}
      >
        <div>
          {/* Brand Header */}
          <div
            className={cn(
              "flex h-[74px] items-center justify-between px-4 border-b transition-colors",
              isLight ? "border-slate-200 bg-slate-50" : "border-[#222] bg-[#090909]"
            )}
          >
            {!collapsed && (
              <Link href="/dashboard" className="flex items-center gap-2.5 group">
                <div
                  className={cn(
                    "w-9 h-9 rounded-lg flex items-center justify-center transition-all shadow-sm",
                    isLight ? "bg-slate-900 text-white" : "bg-[#18181b] border border-[#cf0]/40 text-[#cf0]"
                  )}
                >
                  <Shield className="w-5 h-5" />
                </div>
                <div className="flex flex-col">
                  <span className="font-bold text-base tracking-tight leading-none">TRACE-X</span>
                  <span
                    className={cn(
                      "text-[10px] font-semibold tracking-wider uppercase mt-1",
                      isLight ? "text-emerald-700" : "text-[#cf0]"
                    )}
                  >
                    Forensics Suite
                  </span>
                </div>
              </Link>
            )}
            <button
              onClick={() => setCollapsed(!collapsed)}
              className={cn(
                "p-1.5 rounded-md border transition-colors",
                isLight
                  ? "bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-200"
                  : "bg-[#141414] border-[#262626] text-zinc-400 hover:text-white hover:border-[#cf0]"
              )}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
            </button>
          </div>

          {/* Standard Navigation Items */}
          <nav className="px-3 py-4 space-y-1.5 overflow-y-auto">
            {navigation.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3.5 py-2.5 rounded-md transition-all duration-200 text-xs font-bold uppercase tracking-wider",
                    isActive
                      ? isLight
                        ? "bg-slate-900 text-white shadow-sm font-extrabold border-l-4 border-emerald-500 rounded-l-none pl-3"
                        : "bg-[#cf0]/10 text-[#cf0] font-black border-l-4 border-[#cf0] rounded-l-none pl-3 shadow-[0_0_15px_rgba(204,255,0,0.1)]"
                      : isLight
                      ? "text-slate-600 hover:bg-slate-100 hover:text-slate-900 font-semibold"
                      : "text-zinc-300 hover:bg-[#161616] hover:text-white font-medium",
                    collapsed && "justify-center px-0 border-l-0"
                  )}
                  title={collapsed ? item.name : undefined}
                >
                  <item.icon
                    className={cn(
                      "w-4 h-4 flex-shrink-0 transition-colors",
                      isActive
                        ? isLight
                          ? "text-emerald-400"
                          : "text-[#cf0]"
                        : isLight
                        ? "text-slate-500"
                        : "text-zinc-400"
                    )}
                    aria-hidden="true"
                  />
                  {!collapsed && <span className="truncate">{item.name}</span>}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Informational Sidebar Footer with Logout */}
        <div
          className={cn(
            "p-3 border-t space-y-3 transition-colors",
            isLight ? "border-slate-200 bg-slate-50" : "border-[#222] bg-[#090909]"
          )}
        >
          {!collapsed && (
            <div
              className={cn(
                "rounded-md border p-3 shadow-xs space-y-1",
                isLight
                  ? "bg-white border-slate-200 text-slate-800"
                  : "bg-[#141414] border-[#2a2a2a] text-zinc-300"
              )}
            >
              <div className="flex items-center gap-1.5">
                <Sparkles className={`w-3.5 h-3.5 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />
                <p
                  className={`text-xs font-bold tracking-tight uppercase ${
                    isLight ? "text-emerald-800" : "text-[#cf0]"
                  }`}
                >
                  SIH 2026 • TRACE-X
                </p>
              </div>
              <p
                className={`text-[11px] font-sans leading-snug ${
                  isLight ? "text-slate-600 font-medium" : "text-zinc-300 font-normal"
                }`}
              >
                Real-Time Cryptocurrency Fraud Attribution & Investigation Platform
              </p>
            </div>
          )}

          {/* Sidebar Logout Button */}
          <button
            onClick={handleLogout}
            className={cn(
              "w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md font-mono text-xs font-bold uppercase transition-all border",
              isLight
                ? "bg-red-50 border-red-200 text-red-700 hover:bg-red-100"
                : "bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20"
            )}
            title="Sign out of platform"
          >
            <LogOut className="w-3.5 h-3.5" />
            {!collapsed && <span>LOGOUT</span>}
          </button>
        </div>
      </aside>

      {/* Main Layout Area: Header + Content */}
      <div
        className={cn(
          "flex-1 flex flex-col min-h-screen transition-all duration-300",
          collapsed ? "ml-16" : "ml-[240px]"
        )}
      >
        {/* Global Top Header */}
        <header
          className={cn(
            "h-[74px] border-b px-8 flex items-center justify-between sticky top-0 z-30 shadow-xs backdrop-blur-md transition-colors",
            isLight
              ? "bg-white/95 border-slate-200 text-slate-900"
              : "bg-[#0c0c0c]/90 border-[#222] text-white"
          )}
        >
          {/* Left: Dynamic Title & Subtitle */}
          <div>
            <h1 className="text-lg md:text-xl font-mono font-extrabold uppercase tracking-tight leading-none">
              {currentMeta.title}
            </h1>
            <p
              className={`text-xs font-sans mt-1 ${
                isLight ? "text-slate-600 font-medium" : "text-zinc-300 font-normal"
              }`}
            >
              {currentMeta.subtitle}
            </p>
          </div>

          {/* Right: Universal Actions */}
          <div className="flex items-center gap-3">
            {/* Global Search Pill */}
            <div className="relative hidden md:flex items-center">
              <Search
                className={`w-4 h-4 absolute left-3.5 pointer-events-none ${
                  isLight ? "text-slate-400" : "text-zinc-400"
                }`}
              />
              <input
                type="text"
                placeholder="Search cases, txns, or addresses..."
                className={cn(
                  "w-72 h-10 pl-9 pr-4 text-xs border rounded-full outline-none font-mono transition-all",
                  isLight
                    ? "bg-slate-100 border-slate-300 focus:border-slate-900 focus:bg-white text-slate-900"
                    : "bg-[#161616] border-[#2e2e2e] focus:border-[#cf0] text-white"
                )}
              />
            </div>

            {/* Light / Dark Mode Toggle Button */}
            <button
              onClick={toggleTheme}
              aria-label="Toggle Bright / Dark Mode"
              title={isLight ? "Switch to Cyber Dark Mode" : "Switch to Bright Mode"}
              className={cn(
                "p-2.5 rounded-full border transition-all duration-300",
                isLight
                  ? "bg-slate-100 border-slate-300 text-slate-800 hover:bg-slate-200"
                  : "bg-[#161616] border-[#2a2a2a] text-[#cf0] hover:bg-[#222]"
              )}
            >
              {isLight ? <Moon className="w-4 h-4 text-slate-800" /> : <Sun className="w-4 h-4 text-[#cf0]" />}
            </button>

            {/* Quick Settings Action */}
            <Link
              href="/settings"
              className={cn(
                "w-10 h-10 rounded-full border flex items-center justify-center transition-colors",
                isLight
                  ? "bg-slate-100 border-slate-200 text-slate-700 hover:bg-slate-200"
                  : "bg-[#161616] border-[#2a2a2a] text-zinc-300 hover:text-white hover:border-[#cf0]"
              )}
              title="Platform Settings"
            >
              <Settings className="w-4 h-4" />
            </Link>

            {/* Notification Bell */}
            <button
              className={cn(
                "relative w-10 h-10 rounded-full border flex items-center justify-center transition-colors",
                isLight
                  ? "bg-slate-100 border-slate-200 text-slate-700 hover:bg-slate-200"
                  : "bg-[#161616] border-[#2a2a2a] text-zinc-300 hover:text-white hover:border-[#cf0]"
              )}
              title="Notifications"
            >
              <Bell className="w-4 h-4" />
              <span className="absolute top-2.5 right-2.5 w-2 h-2 rounded-full bg-[#cf0] shadow-[0_0_6px_#cf0] ring-2 ring-black" />
            </button>

            {/* User Profile Avatar & Header Logout */}
            <div
              className={cn(
                "flex items-center gap-3 pl-3 border-l",
                isLight ? "border-slate-200" : "border-[#262626]"
              )}
            >
              <div
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center font-mono font-bold text-xs shadow-xs border",
                  user?.role?.toLowerCase().includes("admin") || user?.role?.toLowerCase().includes("supervisor")
                    ? "bg-amber-500 text-black border-amber-400 font-extrabold"
                    : isLight
                    ? "bg-slate-900 border-slate-900 text-white"
                    : "bg-[#cf0] border-[#cf0] text-black"
                )}
              >
                {user?.full_name ? user.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase() : "SA"}
              </div>
              <div className="hidden lg:flex flex-col">
                <span className="text-xs font-mono font-bold leading-none text-slate-900 dark:text-white">
                  {user?.full_name || "Senior Analyst"}
                </span>
                <div className="flex items-center gap-1 mt-1">
                  <span
                    className={cn(
                      "text-[10px] font-mono px-1.5 py-0.5 rounded font-bold uppercase tracking-wider",
                      user?.role?.toLowerCase().includes("admin") || user?.role?.toLowerCase().includes("supervisor")
                        ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30"
                        : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                    )}
                  >
                    {user?.role?.toLowerCase().includes("admin") || user?.role?.toLowerCase().includes("supervisor")
                      ? "SUPERVISOR & ADMIN"
                      : "ANALYST"}
                  </span>
                  <span className="text-[10px] text-slate-500 dark:text-slate-400 font-mono truncate max-w-[120px]">
                    {user?.email ? user.email.split("@")[0] : ""}
                  </span>
                </div>
              </div>

              {/* Header Logout Icon Button */}
              <button
                onClick={handleLogout}
                title="Sign out of platform"
                className={cn(
                  "p-2 rounded-full border transition-all ml-1",
                  isLight
                    ? "bg-red-50 border-red-200 text-red-600 hover:bg-red-100"
                    : "bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20"
                )}
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </header>

        {/* Page Content Viewport */}
        <main
          className={cn(
            "flex-1 overflow-y-auto p-6 md:p-8 transition-colors duration-300",
            isLight ? "bg-slate-100 text-slate-900" : "bg-[#090909] text-white"
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}