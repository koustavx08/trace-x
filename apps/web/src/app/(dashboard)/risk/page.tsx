"use client";

import { useState } from "react";
import { formatAddress } from "@/lib/utils";
import {
  ShieldAlert,
  ShieldCheck,
  Activity,
  ExternalLink,
  Target,
  BarChart3,
  Layers,
  ArrowUpRight,
} from "lucide-react";
import Link from "next/link";
import { useLandingTheme } from "@/lib/theme-context";

const MOCK_FACTORS = [
  {
    type: "PEEL_CHAIN_DRAINER",
    severity: "CRITICAL",
    score: 96,
    weight: 0.25,
    weighted_score: 24.0,
    confidence: "CONFIRMED (1.0)",
    description: "Multi-hop automated transaction looping through unverified privacy mixer contract.",
  },
  {
    type: "MIXER_ROUTING",
    severity: "HIGH",
    score: 88,
    weight: 0.2,
    weighted_score: 17.6,
    confidence: "HIGH_CONFIDENCE (0.85)",
    description: "Direct input from Tornado Cash ETH 100 pool deposit address.",
  },
  {
    type: "HIGH_VELOCITY_SWEEP",
    severity: "HIGH",
    score: 82,
    weight: 0.15,
    weighted_score: 12.3,
    confidence: "CONFIRMED (1.0)",
    description: "Rapid liquidity sweep within 45 seconds of initial wallet deposit.",
  },
  {
    type: "UNVERIFIED_CONTRACT_INTERACTION",
    severity: "MEDIUM",
    score: 64,
    weight: 0.15,
    weighted_score: 9.6,
    confidence: "PROBABLE (0.65)",
    description: "Execution of non-standard ERC-20 permit approval function.",
  },
  {
    type: "CROSS_CHAIN_BRIDGE_HOP",
    severity: "MEDIUM",
    score: 58,
    weight: 0.15,
    weighted_score: 8.7,
    confidence: "PROBABLE (0.65)",
    description: "Bridging funds via Arbitrum portal to secondary receiver wallet.",
  },
];

export default function RiskPage() {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";
  const walletAddress = "0x71C7656EC7ab88b098defB751B7401B5f6d8976F";

  return (
    <div className="space-y-8 font-mono">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-extrabold uppercase tracking-tight">
            RISK & VASP ATTRIBUTION ENGINE
          </h1>
          <p
            className={`text-xs md:text-sm font-sans mt-1 ${
              isLight ? "text-slate-600 font-medium" : "text-zinc-300 font-normal"
            }`}
          >
            12-Factor Explainable ML Threat Scoring & Dijkstra VASP Entity Attribution
          </p>
        </div>

        <Link
          href={`/graph?address=${walletAddress}`}
          className={`font-mono font-bold text-xs tracking-wider px-5 py-3 rounded-md flex items-center gap-2 uppercase transition-all duration-200 transform hover:scale-[1.02] shadow-sm ${
            isLight
              ? "bg-slate-900 hover:bg-slate-800 text-white"
              : "bg-[#cf0] hover:bg-[#b8e000] text-black shadow-[0_0_15px_rgba(204,255,0,0.2)]"
          }`}
        >
          <ExternalLink className="w-4 h-4" />
          <span>VIEW IN GRAPH CANVAS</span>
        </Link>
      </div>

      {/* Overview Cards */}
      <div className="grid gap-6 md:grid-cols-4">
        <div
          className={`p-6 border rounded-lg transition-colors ${
            isLight
              ? "bg-white border-slate-200 shadow-sm"
              : "bg-[#121212] border-[#262626] shadow-lg"
          }`}
        >
          <p className={`text-xs font-bold uppercase tracking-wider ${isLight ? "text-slate-600" : "text-zinc-400"}`}>
            Target Wallet
          </p>
          <p className="text-base font-bold mt-2 truncate">{formatAddress(walletAddress)}</p>
          <span className="text-[11px] text-emerald-500 font-semibold mt-1 inline-block">ETH MAINNET</span>
        </div>

        <div
          className={`p-6 border rounded-lg transition-colors ${
            isLight
              ? "bg-white border-slate-200 shadow-sm"
              : "bg-[#121212] border-[#262626] shadow-lg"
          }`}
        >
          <p className={`text-xs font-bold uppercase tracking-wider ${isLight ? "text-slate-600" : "text-zinc-400"}`}>
            Calculated Risk Level
          </p>
          <p className="text-3xl font-black text-red-500 mt-1">CRITICAL</p>
          <span className="text-[11px] text-red-400 font-semibold">Score: 92.4 / 100</span>
        </div>

        <div
          className={`p-6 border rounded-lg transition-colors ${
            isLight
              ? "bg-white border-slate-200 shadow-sm"
              : "bg-[#121212] border-[#262626] shadow-lg"
          }`}
        >
          <p className={`text-xs font-bold uppercase tracking-wider ${isLight ? "text-slate-600" : "text-zinc-400"}`}>
            Attributed VASP
          </p>
          <p className="text-lg font-bold mt-2 text-amber-500">BINANCE HOT WALLET</p>
          <span className="text-[11px] text-zinc-400">Distance: 3 Hops</span>
        </div>

        <div
          className={`p-6 border rounded-lg transition-colors ${
            isLight
              ? "bg-white border-slate-200 shadow-sm"
              : "bg-[#121212] border-[#262626] shadow-lg"
          }`}
        >
          <p className={`text-xs font-bold uppercase tracking-wider ${isLight ? "text-slate-600" : "text-zinc-400"}`}>
            Model Confidence
          </p>
          <p className={`text-3xl font-black mt-1 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`}>
            98.4%
          </p>
          <span className="text-[11px] text-zinc-400">CONFIRMED (1.0)</span>
        </div>
      </div>

      {/* 12-Factor Threat Breakdown Table */}
      <div
        className={`p-6 border rounded-lg transition-colors ${
          isLight
            ? "bg-white border-slate-200 shadow-sm"
            : "bg-[#121212] border-[#262626] shadow-lg"
        }`}
      >
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-200 dark:border-[#222]">
          <div>
            <h2 className="text-lg font-bold uppercase tracking-wide">
              12-FACTOR EXPLAINABLE THREAT MATRIX
            </h2>
            <p className={`text-xs font-sans mt-0.5 ${isLight ? "text-slate-600" : "text-zinc-300"}`}>
              Weighted threat factors evaluated by TRACE-AI attribution engine
            </p>
          </div>
          <span className={`px-3 py-1 text-xs font-bold uppercase rounded-full border ${
            isLight ? "bg-red-50 border-red-300 text-red-700" : "bg-red-500/10 border-red-500/40 text-red-400"
          }`}>
            CRITICAL THREAT LEVEL
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr
                className={`border-b text-[11px] uppercase tracking-wider ${
                  isLight
                    ? "border-slate-200 text-slate-600 bg-slate-50"
                    : "border-[#222] text-zinc-400 bg-[#161616]"
                }`}
              >
                <th className="p-4">Threat Factor</th>
                <th className="p-4">Severity</th>
                <th className="p-4">Score</th>
                <th className="p-4">Weight</th>
                <th className="p-4">Weighted Score</th>
                <th className="p-4">Confidence Rating</th>
                <th className="p-4">Heuristic Evidence Summary</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-[#1f1f1f]">
              {MOCK_FACTORS.map((factor) => (
                <tr key={factor.type} className="hover:bg-slate-50 dark:hover:bg-[#181818] transition-colors">
                  <td className="p-4 font-bold">{factor.type.replace(/_/g, " ")}</td>
                  <td className="p-4">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase border ${
                        factor.severity === "CRITICAL"
                          ? "bg-red-500/10 text-red-400 border-red-500/40"
                          : "bg-amber-500/10 text-amber-500 border-amber-500/40"
                      }`}
                    >
                      {factor.severity}
                    </span>
                  </td>
                  <td className="p-4 font-bold">{factor.score} / 100</td>
                  <td className="p-4">{factor.weight}</td>
                  <td className={`p-4 font-black ${isLight ? "text-emerald-700" : "text-[#cf0]"}`}>
                    {factor.weighted_score.toFixed(1)}
                  </td>
                  <td className="p-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${isLight ? "bg-slate-100 border-slate-300 text-slate-800" : "bg-[#1a1a1a] border-[#333] text-zinc-300"}`}>
                      {factor.confidence}
                    </span>
                  </td>
                  <td className={`p-4 max-w-xs font-sans ${isLight ? "text-slate-700" : "text-zinc-300"}`}>
                    {factor.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}