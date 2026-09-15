"use client";

import Link from "next/link";
import { ArrowLeft, Terminal } from "lucide-react";
import { useLandingTheme } from "@/lib/theme-context";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";

  return (
    <div
      className={`min-h-screen flex flex-col justify-between relative font-mono overflow-x-hidden transition-colors duration-300 ${
        isLight
          ? "bg-slate-50 text-slate-900 selection:bg-slate-900 selection:text-white"
          : "bg-[#070707] text-white selection:bg-[#cf0] selection:text-black"
      }`}
    >
      {/* Background Cyber Overlay Grid */}
      <div
        className={`absolute inset-0 pointer-events-none opacity-25 ${
          isLight
            ? "bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f0_1px,transparent_1px)] bg-[size:4rem_4rem]"
            : "bg-[linear-gradient(to_right,#1f2937_1px,transparent_1px),linear-gradient(to_bottom,#1f2937_1px,transparent_1px)] bg-[size:4rem_4rem]"
        }`}
      />

      {/* Header */}
      <header
        className={`fixed top-0 left-0 right-0 z-50 backdrop-blur-md border-b px-6 md:px-12 py-4 transition-colors ${
          isLight
            ? "bg-white/95 border-slate-200 shadow-sm"
            : "bg-[#0a0a0a]/90 border-[#333]"
        }`}
      >
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group">
            <div
              className={`w-2.5 h-2.5 rounded-full animate-pulse ${
                isLight ? "bg-emerald-600 shadow-[0_0_10px_#10b981]" : "bg-[#cf0] shadow-[0_0_10px_#cf0]"
              }`}
            />
            <span
              className={`text-base md:text-lg tracking-[2.5px] uppercase font-bold transition-colors ${
                isLight ? "text-slate-900 group-hover:text-emerald-600" : "text-white group-hover:text-[#cf0]"
              }`}
            >
              TRACE-X
            </span>
          </Link>

          <div className="flex items-center gap-4">
            <div
              className={`hidden sm:flex items-center gap-2 px-3 py-1 text-xs font-mono-share border ${
                isLight
                  ? "bg-emerald-50 border-emerald-300 text-emerald-800"
                  : "bg-[rgba(204,255,0,0.05)] border-[rgba(204,255,0,0.3)] text-[#cf0]"
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              <span>GATEWAY SECURED</span>
            </div>

            <Link
              href="/"
              className={`flex items-center gap-2 text-xs uppercase font-bold tracking-wider px-3.5 py-2 border transition-all ${
                isLight
                  ? "bg-white border-slate-300 text-slate-800 hover:border-slate-900"
                  : "bg-[#121212] border-[#333] text-[#aaa] hover:text-white hover:border-[#cf0]"
              }`}
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>RETURN TO LANDING</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Main Form Box */}
      <main className="flex-1 flex items-center justify-center px-4 pt-28 pb-16 z-10 relative">
        <div className="w-full max-w-md">{children}</div>
      </main>

      {/* Telemetry Footer */}
      <footer
        className={`border-t py-4 px-6 text-center text-xs transition-colors ${
          isLight
            ? "border-slate-200 bg-white text-slate-500"
            : "border-[#222] bg-[#0a0a0a] text-[#555]"
        }`}
      >
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>{"//TRACE-X OPERATOR AUTHENTICATION v2.5.1"}</span>
          <span>PGP ENCRYPTED TLS 1.3 SESSION</span>
        </div>
      </footer>
    </div>
  );
}
