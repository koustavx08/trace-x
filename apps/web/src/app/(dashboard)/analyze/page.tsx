"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { formatAddress, formatCurrency, formatRelativeTime } from "@/lib/utils";
import { analysisApi } from "@/lib/api";
import {
  Search,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  Activity,
  Download,
  XCircle,
  CheckCircle2,
  ExternalLink,
  Bot,
  Filter,
} from "lucide-react";
import { useLandingTheme } from "@/lib/theme-context";
import Link from "next/link";

interface ChainInfo {
  chain_id: number;
  name: string;
  symbol: string;
  explorer: string;
  rpc_env: string;
}

interface Transaction {
  tx_hash: string;
  block_number: number;
  timestamp: string;
  from_address: string;
  to_address: string;
  value: string;
  value_usd?: number;
  token_address?: string;
  token_symbol?: string;
  method?: string;
  is_suspicious: boolean;
}

interface Pattern {
  type: string;
  severity: "High" | "Medium" | "Low";
  description: string;
  wallets: number;
}

export default function AnalyzePage() {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";

  const [address, setAddress] = useState("0xa241ec91A7D0c2c8bf11d01C168579Ee1201a209");
  const [chainId, setChainId] = useState<number | undefined>(1);
  const [depth, setDepth] = useState(5);
  const [analyzing, setAnalyzing] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{ valid: boolean; error?: string } | null>({ valid: true });
  const [results, setResults] = useState<Transaction[] | null>(null);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [traceResult, setTraceResult] = useState<any>(null);
  const [chains, setChains] = useState<ChainInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"transactions" | "patterns" | "graph">("transactions");

  useEffect(() => {
    loadChains();
  }, []);

  const loadChains = async () => {
    try {
      const response = await analysisApi.listChains();
      setChains(response.chains);
    } catch {
      setChains([
        { chain_id: 1, name: "Ethereum Mainnet", symbol: "ETH", explorer: "etherscan.io", rpc_env: "ETH_RPC" },
        { chain_id: 137, name: "Polygon Mainnet", symbol: "MATIC", explorer: "polygonscan.com", rpc_env: "POLYGON_RPC" },
        { chain_id: 42161, name: "Arbitrum One", symbol: "ETH", explorer: "arbiscan.io", rpc_env: "ARB_RPC" },
      ]);
    }
  };

  const validateAddress = async () => {
    if (!address || address.length < 10) {
      setValidationResult({ valid: false, error: "Address too short" });
      return;
    }
    setValidating(true);
    setValidationResult({ valid: true });
    setValidating(false);
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!address) return;

    setAnalyzing(true);
    setError(null);

    setTimeout(() => {
      const mockTxs: Transaction[] = [
        {
          tx_hash: "0x3f8a91b2c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f90123456789abcdef01234567",
          block_number: 19482019,
          timestamp: new Date().toISOString(),
          from_address: address,
          to_address: "0x71C7656EC7ab88b098defB751B7401B5f6d8976F",
          value: "14.5",
          value_usd: 48500,
          token_symbol: "ETH",
          method: "transfer",
          is_suspicious: true,
        },
        {
          tx_hash: "0x1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f90123456789abcdef0123456789",
          block_number: 19481950,
          timestamp: new Date(Date.now() - 3600000).toISOString(),
          from_address: "0x098B716B8Aaf21512996dC57EB0615e2383E2f96",
          to_address: address,
          value: "25.0",
          value_usd: 83500,
          token_symbol: "ETH",
          method: "deposit",
          is_suspicious: true,
        },
      ];
      setResults(mockTxs);
      setPatterns([
        {
          type: "Peel Chain Drainer",
          severity: "High",
          description: "4 rapid transactions moving funds into unverified privacy mixer contract.",
          wallets: 3,
        },
        {
          type: "High-Frequency Hop",
          severity: "Medium",
          description: "Sub-second transaction relay through multi-sig wallet cluster.",
          wallets: 2,
        },
      ]);
      setAnalyzing(false);
    }, 800);
  };

  return (
    <div className="space-y-8 font-mono">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-extrabold uppercase tracking-tight">
          SINGLE & MULTI-WALLET ANALYZER
        </h1>
        <p
          className={`text-xs md:text-sm font-sans mt-1 ${
            isLight ? "text-slate-600 font-medium" : "text-zinc-300 font-normal"
          }`}
        >
          Recursive fund flow tracing, on-chain address validation & heuristic pattern detection
        </p>
      </div>

      {/* Analysis Form Card */}
      <div
        className={`p-6 border rounded-lg transition-colors ${
          isLight
            ? "bg-white border-slate-200 shadow-sm"
            : "bg-[#121212] border-[#262626] shadow-lg"
        }`}
      >
        <form onSubmit={handleAnalyze} className="space-y-6">
          <div className="grid gap-6 md:grid-cols-3">
            <div className="md:col-span-2 space-y-2">
              <label className="block text-xs uppercase font-bold tracking-wider">
                Target Wallet / Contract Address *
              </label>
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="relative flex-1">
                  <input
                    type="text"
                    placeholder="0x... or 7x..."
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    onBlur={validateAddress}
                    required
                    className={`w-full border px-4 py-3 text-xs outline-none transition-colors ${
                      isLight
                        ? "bg-slate-50 border-slate-300 focus:border-slate-900 text-slate-900"
                        : "bg-[#161616] border-[#333] focus:border-[#cf0] text-white"
                    }`}
                  />
                  {validating && (
                    <Activity className="w-4 h-4 absolute right-3 top-3 animate-spin text-amber-500" />
                  )}
                  {validationResult?.valid && !validating && (
                    <CheckCircle2 className="w-4 h-4 absolute right-3 top-3 text-emerald-500" />
                  )}
                </div>

                <select
                  value={chainId || 1}
                  onChange={(e) => setChainId(parseInt(e.target.value))}
                  className={`border px-4 py-3 text-xs outline-none transition-colors ${
                    isLight
                      ? "bg-slate-50 border-slate-300 text-slate-900"
                      : "bg-[#161616] border-[#333] text-white"
                  }`}
                >
                  {chains.map((c) => (
                    <option key={c.chain_id} value={c.chain_id}>
                      {c.name} ({c.symbol})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-xs uppercase font-bold tracking-wider">
                Trace Hop Depth
              </label>
              <select
                value={depth}
                onChange={(e) => setDepth(parseInt(e.target.value))}
                className={`w-full border px-4 py-3 text-xs outline-none transition-colors ${
                  isLight
                    ? "bg-slate-50 border-slate-300 text-slate-900"
                    : "bg-[#161616] border-[#333] text-white"
                }`}
              >
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((d) => (
                  <option key={d} value={d}>
                    {d} Hops Deep
                  </option>
                ))}
              </select>
            </div>
          </div>

          {error && (
            <div className="p-3 border border-red-500/40 bg-red-500/10 text-red-400 text-xs font-mono">
              {error}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-100 dark:border-[#222]">
            <button
              type="submit"
              disabled={analyzing || !address}
              className={`font-mono font-bold text-xs tracking-wider px-6 py-3.5 flex items-center gap-2 uppercase transition-all ${
                isLight
                  ? "bg-slate-900 hover:bg-slate-800 text-white shadow-sm"
                  : "bg-[#cf0] hover:bg-[#b8e000] text-black shadow-[0_0_15px_rgba(204,255,0,0.2)]"
              }`}
            >
              {analyzing ? (
                <>
                  <Activity className="w-4 h-4 animate-spin" />
                  <span>ANALYZING ON-CHAIN...</span>
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  <span>RUN WALLET ANALYSIS</span>
                </>
              )}
            </button>

            <Link
              href={`/graph?address=${address}`}
              className={`font-mono font-bold text-xs tracking-wider px-5 py-3.5 border flex items-center gap-2 uppercase transition-colors ${
                isLight
                  ? "bg-white border-slate-300 text-slate-900 hover:bg-slate-50"
                  : "bg-[#161616] border-[#333] text-white hover:border-[#cf0]"
              }`}
            >
              <ExternalLink className="w-4 h-4 text-[#cf0]" />
              <span>OPEN GRAPH CANVAS</span>
            </Link>
          </div>
        </form>
      </div>

      {/* Tabs / Results */}
      {results && (
        <div className="space-y-6">
          <div className="flex items-center gap-2 border-b border-slate-200 dark:border-[#222] pb-3">
            <button
              onClick={() => setActiveTab("transactions")}
              className={`px-4 py-2 text-xs font-bold uppercase transition-colors border-b-2 -mb-3 ${
                activeTab === "transactions"
                  ? isLight
                    ? "border-slate-900 text-slate-900 font-extrabold"
                    : "border-[#cf0] text-[#cf0] font-extrabold"
                  : isLight
                  ? "border-transparent text-slate-500 hover:text-slate-900"
                  : "border-transparent text-zinc-400 hover:text-white"
              }`}
            >
              TRANSACTIONS ({results.length})
            </button>
            <button
              onClick={() => setActiveTab("patterns")}
              className={`px-4 py-2 text-xs font-bold uppercase transition-colors border-b-2 -mb-3 ${
                activeTab === "patterns"
                  ? isLight
                    ? "border-slate-900 text-slate-900 font-extrabold"
                    : "border-[#cf0] text-[#cf0] font-extrabold"
                  : isLight
                  ? "border-transparent text-slate-500 hover:text-slate-900"
                  : "border-transparent text-zinc-400 hover:text-white"
              }`}
            >
              PATTERNS DETECTED ({patterns.length})
            </button>
          </div>

          {activeTab === "transactions" && (
            <div
              className={`border rounded-lg overflow-hidden ${
                isLight
                  ? "bg-white border-slate-200 shadow-sm"
                  : "bg-[#121212] border-[#262626] shadow-lg"
              }`}
            >
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr
                      className={`border-b text-[11px] uppercase tracking-wider ${
                        isLight ? "border-slate-200 text-slate-600 bg-slate-50" : "border-[#222] text-zinc-400 bg-[#161616]"
                      }`}
                    >
                      <th className="p-4">Tx Hash</th>
                      <th className="p-4">Block</th>
                      <th className="p-4">Time</th>
                      <th className="p-4">From</th>
                      <th className="p-4">To</th>
                      <th className="p-4">Value (USD)</th>
                      <th className="p-4">Token</th>
                      <th className="p-4">Risk Flag</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-[#1f1f1f]">
                    {results.map((tx) => (
                      <tr key={tx.tx_hash} className="hover:bg-slate-50 dark:hover:bg-[#181818] transition-colors">
                        <td className="p-4 font-bold">{formatAddress(tx.tx_hash)}</td>
                        <td className="p-4">#{tx.block_number}</td>
                        <td className={`p-4 ${isLight ? "text-slate-600" : "text-zinc-400"}`}>
                          {formatRelativeTime(tx.timestamp)}
                        </td>
                        <td className="p-4 font-bold">{formatAddress(tx.from_address)}</td>
                        <td className="p-4 font-bold">{formatAddress(tx.to_address)}</td>
                        <td className={`p-4 font-black ${isLight ? "text-emerald-700" : "text-[#cf0]"}`}>
                          {formatCurrency(tx.value_usd || 0)}
                        </td>
                        <td className="p-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${isLight ? "bg-slate-100 border-slate-300 text-slate-800" : "bg-[#1a1a1a] border-[#333] text-zinc-300"}`}>
                            {tx.token_symbol || "ETH"}
                          </span>
                        </td>
                        <td className="p-4">
                          {tx.is_suspicious && (
                            <span className="px-2 py-1 bg-red-500/10 border border-red-500/40 text-red-400 text-[10px] font-bold uppercase rounded inline-flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3 text-red-500" />
                              <span>HIGH RISK</span>
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === "patterns" && (
            <div className="space-y-4">
              {patterns.map((pattern) => (
                <div
                  key={pattern.type}
                  className={`p-5 rounded-lg border flex items-center justify-between gap-4 ${
                    isLight
                      ? "bg-white border-slate-200 shadow-sm"
                      : "bg-[#121212] border-[#262626] shadow-lg"
                  }`}
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-mono text-sm font-bold">{pattern.type}</h4>
                      <span className="px-2 py-0.5 bg-red-500/10 border border-red-500/40 text-red-400 text-[10px] font-bold uppercase rounded">
                        SEVERITY: {pattern.severity}
                      </span>
                    </div>
                    <p className={`text-xs font-sans ${isLight ? "text-slate-600 font-medium" : "text-zinc-300"}`}>
                      {pattern.description}
                    </p>
                  </div>
                  <span className={`text-xs font-mono font-bold ${isLight ? "text-slate-500" : "text-zinc-400"}`}>
                    {pattern.wallets} Nodes
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}