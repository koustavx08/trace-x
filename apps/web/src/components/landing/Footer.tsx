"use client";

import Link from "next/link";
import { useLandingTheme } from "@/lib/theme-context";

export default function Footer() {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";

  return (
    <footer
      className={`border-t px-6 md:px-12 py-16 transition-colors duration-300 ${
        isLight
          ? "bg-slate-50 border-slate-200 text-slate-900"
          : "bg-[#070707] border-[#262626] text-white"
      }`}
    >
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-12">
        {/* Left — brand */}
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-2">
            <div
              className={`w-3 h-3 rounded-full ${
                isLight
                  ? "bg-emerald-600 shadow-[0_0_10px_#10b981]"
                  : "bg-[#cf0] shadow-[0_0_10px_#cf0]"
              }`}
            />
            <span className="text-2xl font-bold tracking-tight font-mono">
              TRACE-X
            </span>
          </div>
          <p
            className={`text-sm font-sans leading-relaxed max-w-sm ${
              isLight ? "text-slate-700 font-medium" : "text-zinc-300 font-normal"
            }`}
          >
            An independent crypto fraud attribution platform. Surfacing on-chain deception through systematic analysis, GNN clustering, and raw blockchain data. Dedicated to transparency.
          </p>
          <p
            className={`text-xs font-mono font-semibold ${
              isLight ? "text-slate-500" : "text-zinc-500"
            }`}
          >
            © {new Date().getFullYear()} TRACE-X. ARCHITECTS OF TRUTH.
          </p>
        </div>

        {/* Middle — stats */}
        <div className="flex flex-col gap-4">
          <p
            className={`text-xs font-mono tracking-[1.5px] font-extrabold uppercase ${
              isLight ? "text-emerald-700" : "text-[#cf0]"
            }`}
          >
            SYSTEM TELEMETRY STATS
          </p>
          <div className="flex flex-col gap-3 font-mono-share text-sm">
            {[
              "ACTIVE CASES: 247",
              "WALLETS FLAGGED: 38,412",
              "CHAINS: ETH / BTC / BSC / SOL / ARB",
              "STATUS: ALL SYSTEMS GO",
            ].map((line) => (
              <p
                key={line}
                className={`font-semibold ${isLight ? "text-slate-700" : "text-zinc-200"}`}
              >
                {line}
              </p>
            ))}
          </div>
        </div>

        {/* Right — links */}
        <div className="flex flex-col gap-4">
          <p
            className={`text-xs font-mono tracking-[1.5px] font-extrabold uppercase ${
              isLight ? "text-emerald-700" : "text-[#cf0]"
            }`}
          >
            NAVIGATION LINKS
          </p>
          <div className="flex flex-col gap-3 font-mono text-sm">
            <a
              href="#how-it-works"
              className={`transition-colors ${
                isLight ? "text-slate-700 hover:text-black font-semibold" : "text-zinc-300 hover:text-[#cf0]"
              }`}
            >
              HOW IT WORKS
            </a>
            <a
              href="#team"
              className={`transition-colors ${
                isLight ? "text-slate-700 hover:text-black font-semibold" : "text-zinc-300 hover:text-[#cf0]"
              }`}
            >
              ABOUT THE TEAM
            </a>
            <Link
              href="/login"
              className={`transition-colors ${
                isLight ? "text-slate-700 hover:text-black font-semibold" : "text-zinc-300 hover:text-[#cf0]"
              }`}
            >
              OPERATOR LOGIN
            </Link>
            <Link
              href="/dashboard"
              className={`transition-colors ${
                isLight ? "text-slate-700 hover:text-black font-semibold" : "text-zinc-300 hover:text-[#cf0]"
              }`}
            >
              INVESTIGATION DASHBOARD
            </Link>
          </div>
        </div>
      </div>

      <div
        className={`max-w-7xl mx-auto mt-16 border-t pt-6 flex flex-col md:flex-row items-center justify-between gap-4 font-mono ${
          isLight ? "border-slate-200" : "border-[#262626]"
        }`}
      >
        <p className={isLight ? "text-slate-500 text-xs font-semibold" : "text-zinc-400 text-xs"}>
          {`//SYSTEM ONLINE — TRACE-X v2.5.1`}
        </p>
        <div
          className={`flex items-center gap-2 px-3 py-1.5 border rounded-full ${
            isLight
              ? "bg-emerald-50 border-emerald-300 text-emerald-800"
              : "bg-[rgba(204,255,0,0.05)] border-[rgba(204,255,0,0.3)] text-[#cf0]"
          }`}
        >
          <div
            className={`w-2 h-2 rounded-full animate-pulse ${
              isLight ? "bg-emerald-600 shadow-[0_0_6px_#10b981]" : "bg-[#cf0] shadow-[0_0_6px_#cf0]"
            }`}
          />
          <span className="text-xs font-mono-share tracking-[1px] font-bold">
            MONITORING ACTIVE
          </span>
        </div>
      </div>
    </footer>
  );
}
