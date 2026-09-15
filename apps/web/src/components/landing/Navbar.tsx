"use client";

import Link from "next/link";
import { Sun, Moon } from "lucide-react";
import { useAuthStore } from "@/store/auth-store";
import { useLandingTheme } from "@/lib/theme-context";

export default function Navbar() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { theme, toggleTheme } = useLandingTheme();
  const isLight = theme === "light";

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 backdrop-blur-md border-b transition-colors duration-300 ${
        isLight
          ? "bg-white/95 border-slate-200 shadow-sm"
          : "bg-[#0a0a0a]/90 border-[#262626]"
      }`}
    >
      <div className="flex items-center justify-between px-6 md:px-12 py-4 max-w-7xl mx-auto">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-3 group">
          <div
            className={`w-2.5 h-2.5 rounded-full animate-pulse ${
              isLight
                ? "bg-emerald-600 shadow-[0_0_10px_#10b981]"
                : "bg-[#cf0] shadow-[0_0_10px_#cf0]"
            }`}
          />
          <span
            className={`text-base md:text-lg tracking-[2.5px] uppercase font-bold font-mono transition-colors ${
              isLight
                ? "text-slate-900 group-hover:text-emerald-600"
                : "text-white group-hover:text-[#cf0]"
            }`}
          >
            TRACE-X
          </span>
        </Link>

        {/* Desktop Nav Links */}
        <div
          className={`hidden md:flex items-center gap-10 text-sm tracking-[1.5px] uppercase font-mono font-medium transition-colors ${
            isLight ? "text-slate-700" : "text-zinc-300"
          }`}
        >
          <a
            href="#how-it-works"
            className={`transition-colors ${
              isLight ? "hover:text-black font-semibold" : "hover:text-[#cf0]"
            }`}
          >
            How It Works
          </a>
          <a
            href="#team"
            className={`transition-colors ${
              isLight ? "hover:text-black font-semibold" : "hover:text-[#cf0]"
            }`}
          >
            About the Team
          </a>
        </div>

        {/* Telemetry & Theme Toggle & Action Buttons */}
        <div className="flex items-center gap-3 md:gap-4">
          <div
            className={`hidden lg:flex items-center gap-2 px-3 py-1.5 font-mono-share rounded-full transition-colors ${
              isLight
                ? "bg-emerald-50 border border-emerald-300 text-emerald-800"
                : "bg-[rgba(204,255,0,0.05)] border border-[rgba(204,255,0,0.3)] text-[#cf0]"
            }`}
          >
            <div
              className={`w-2 h-2 rounded-full animate-ping ${
                isLight ? "bg-emerald-600" : "bg-[#cf0]"
              }`}
            />
            <span className="text-xs tracking-[1px] uppercase font-bold">
              LIVE MONITORING
            </span>
          </div>

          {/* Light / Dark Mode Toggle Button */}
          <button
            onClick={toggleTheme}
            aria-label="Toggle Bright / Dark Mode"
            title={isLight ? "Switch to Cyber Dark Mode" : "Switch to Bright Mode"}
            className={`p-2 rounded-md border transition-all duration-300 ${
              isLight
                ? "bg-slate-100 border-slate-300 text-slate-800 hover:bg-slate-200"
                : "bg-[#141414] border-[#333] text-[#cf0] hover:bg-[#222]"
            }`}
          >
            {isLight ? (
              <Moon className="w-4 h-4 text-slate-800" />
            ) : (
              <Sun className="w-4 h-4 text-[#cf0]" />
            )}
          </button>

          <Link
            href={isAuthenticated ? "/dashboard" : "/login"}
            className={`font-mono font-bold text-xs tracking-wider px-5 py-2.5 uppercase transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] ${
              isLight
                ? "bg-slate-900 hover:bg-slate-800 text-white shadow-sm"
                : "bg-[#cf0] hover:bg-[#b8e000] text-black shadow-[0_0_15px_rgba(204,255,0,0.2)]"
            }`}
          >
            {isAuthenticated ? "Dashboard" : "Launch App"}
          </Link>
        </div>
      </div>
    </nav>
  );
}
