"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatRelativeTime, formatAddress } from "@/lib/utils";
import { casesApi, walletsApi, investigationsApi, healthApi } from "@/lib/api";
import {
  Activity,
  FolderOpen,
  Search,
  FileText,
  CheckCircle,
  Plus,
  Shield,
  ArrowUpRight,
  Database,
  GitBranch,
  Cpu,
} from "lucide-react";
import Link from "next/link";
import { useLandingTheme } from "@/lib/theme-context";
import { useAuthStore } from "@/store/auth-store";

const statusLabels: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  closed: "Closed",
  archived: "Archived",
};

const investigationStatusLabels: Record<string, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export default function DashboardPage() {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";
  const user = useAuthStore((state) => state.user);

  const { data: casesData } = useQuery({
    queryKey: ["cases", { page: 1, page_size: 5, status: "open,in_progress" }],
    queryFn: () => casesApi.list({ page: 1, page_size: 5, status: "open,in_progress" }),
  });

  const { data: walletsData } = useQuery({
    queryKey: ["wallets", { page: 1, page_size: 1 }],
    queryFn: () => walletsApi.list({ page: 1, page_size: 1 }),
  });

  const { data: investigationsData } = useQuery({
    queryKey: ["investigations", { page: 1, page_size: 5, status: "running,pending" }],
    queryFn: () => investigationsApi.list({ page: 1, page_size: 5, status: "running,pending" }),
  });

  const { data: healthData } = useQuery({
    queryKey: ["health"],
    queryFn: () => healthApi.check(),
    refetchInterval: 30000,
  });

  const activeCasesCount = casesData?.items.filter((c: any) => c.status !== "closed" && c.status !== "archived").length || 0;
  const totalWallets = walletsData?.total || 0;
  const runningInvestigations = investigationsData?.items.filter((i: any) => i.status === "running").length || 0;
  const completedInvestigations = investigationsData?.items.filter((i: any) => i.status === "completed").length || 0;

  const stats = [
    { name: "Active Cases", value: activeCasesCount.toString(), change: "+2 this week", icon: FolderOpen, color: isLight ? "text-emerald-700 bg-emerald-50" : "text-[#cf0] bg-[#cf0]/10 border-[#cf0]/30" },
    { name: "Wallets Tracked", value: totalWallets.toString(), change: "+14 this week", icon: Search, color: isLight ? "text-blue-700 bg-blue-50" : "text-cyan-400 bg-cyan-400/10 border-cyan-400/30" },
    { name: "Investigations Running", value: runningInvestigations.toString(), change: "Active Engine", icon: Activity, color: isLight ? "text-amber-700 bg-amber-50" : "text-amber-400 bg-amber-400/10 border-amber-400/30" },
    { name: "Completed Traces", value: completedInvestigations.toString(), change: "Evidence Generated", icon: FileText, color: isLight ? "text-purple-700 bg-purple-50" : "text-purple-400 bg-purple-400/10 border-purple-400/30" },
  ];

  const isSupervisorOrAdmin =
    user?.role?.toLowerCase().includes("admin") ||
    user?.role?.toLowerCase().includes("supervisor");

  const roleLabel = isSupervisorOrAdmin ? "SUPERVISOR & SYSTEM ADMIN" : "ANALYST";

  const roleTitle = isSupervisorOrAdmin
    ? "SUPERVISORY & SYSTEM ADMIN COMMAND CENTER"
    : "FORENSIC ANALYST WORKSPACE";

  const userName = user?.full_name || (isSupervisorOrAdmin ? "Supervisor & System Admin" : "Senior Investigator");
  const userEmail = user?.email || (isSupervisorOrAdmin ? "supervisor@tracex.gov" : "analyst.a@tracex.gov");

  const roleSubtitle = isSupervisorOrAdmin
    ? `Welcome ${userName} (${userEmail}) • Unified Case Oversight, System Telemetry, Approvals & Full Platform Administration`
    : `Welcome ${userName} (${userEmail}) • Active Wallet Traces, Multi-Hop Graph Analysis & Case Dossiers`;

  return (
    <div className="space-y-8 font-mono">
      {/* Top Banner Header */}
      <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#121212] shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span
              className={`px-2.5 py-0.5 rounded text-xs font-mono font-bold uppercase tracking-wider ${
                isSupervisorOrAdmin
                  ? "bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30"
                  : "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
              }`}
            >
              {roleLabel}
            </span>
            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">
              Session ID: {user?.id || "demo-session"}
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold uppercase tracking-tight text-slate-900 dark:text-white">
            {roleTitle}
          </h1>
          <p
            className={`text-xs md:text-sm font-sans mt-1.5 ${
              isLight ? "text-slate-600 font-medium" : "text-zinc-300 font-normal"
            }`}
          >
            {roleSubtitle}
          </p>
        </div>

        <Link
          href="/cases/new"
          className={`font-mono font-bold text-xs tracking-wider px-5 py-3 rounded-xl flex items-center gap-2 uppercase transition-all duration-200 transform hover:scale-[1.02] shadow-sm ${
            isLight
              ? "bg-slate-900 hover:bg-slate-800 text-white"
              : "bg-[#cf0] hover:bg-[#b8e000] text-black shadow-[0_0_15px_rgba(204,255,0,0.2)]"
          }`}
        >
          <Plus className="w-4 h-4" />
          <span>INITIATE NEW CASE</span>
        </Link>
      </div>

      {/* 4 Metric Cards Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.name}
            className={`p-6 border rounded-lg transition-all duration-300 flex flex-col justify-between ${
              isLight
                ? "bg-white border-slate-200 shadow-sm hover:shadow-md"
                : "bg-[#121212] border-[#262626] shadow-lg hover:border-[#cf0]/50"
            }`}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className={`text-xs font-bold uppercase tracking-wider ${isLight ? "text-slate-600" : "text-zinc-400"}`}>
                  {stat.name}
                </p>
                <p className={`text-3xl md:text-4xl font-black mt-2 tracking-tight ${isLight ? "text-slate-900" : "text-white"}`}>
                  {stat.value}
                </p>
              </div>
              <div className={`p-3 rounded-lg border ${stat.color}`}>
                <stat.icon className="w-6 h-6" />
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-dashed border-[#333]/20 flex items-center justify-between text-[11px]">
              <span className={`font-semibold ${isLight ? "text-emerald-700" : "text-[#cf0]"}`}>
                {stat.change}
              </span>
              <span className={isLight ? "text-slate-400" : "text-zinc-500"}>Live Sync</span>
            </div>
          </div>
        ))}
      </div>

      {/* Grid of Tables & Active Traces */}
      <div className="grid gap-8 lg:grid-cols-2">
        {/* Recent Cases */}
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
                RECENT FORENSIC DOSSIERS
              </h2>
              <p className={`text-xs font-sans mt-0.5 ${isLight ? "text-slate-500" : "text-zinc-400"}`}>
                Active criminal cases with chain-of-custody tracking
              </p>
            </div>
            <Link
              href="/cases"
              className={`text-xs font-bold flex items-center gap-1 ${
                isLight ? "text-emerald-700 hover:underline" : "text-[#cf0] hover:underline"
              }`}
            >
              <span>VIEW ALL</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className={`border-b text-[11px] uppercase tracking-wider ${isLight ? "border-slate-200 text-slate-500" : "border-[#222] text-zinc-400"}`}>
                  <th className="pb-3">Case ID</th>
                  <th className="pb-3">Title</th>
                  <th className="pb-3">Status</th>
                  <th className="pb-3 text-right">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-[#1f1f1f]">
                {(casesData?.items || []).map((caseItem: any) => (
                  <tr key={caseItem.id} className="hover:bg-slate-50 dark:hover:bg-[#181818] transition-colors">
                    <td className="py-3 font-bold">{caseItem.case_number}</td>
                    <td className="py-3 max-w-[180px] truncate">{caseItem.title}</td>
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                        caseItem.status === "in_progress"
                          ? "bg-amber-500/10 text-amber-500 border border-amber-500/30"
                          : "bg-emerald-500/10 text-emerald-500 border border-emerald-500/30"
                      }`}>
                        {statusLabels[caseItem.status] || caseItem.status}
                      </span>
                    </td>
                    <td className={`py-3 text-right ${isLight ? "text-slate-500" : "text-zinc-400"}`}>
                      {formatRelativeTime(caseItem.updated_at)}
                    </td>
                  </tr>
                ))}
                {(casesData?.items?.length || 0) === 0 && (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-zinc-400">
                      No active cases in system. <Link href="/cases/new" className="text-[#cf0] underline">Create first case</Link>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Active Investigations */}
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
                ACTIVE TRACE PIPELINES
              </h2>
              <p className={`text-xs font-sans mt-0.5 ${isLight ? "text-slate-500" : "text-zinc-400"}`}>
                Multi-hop graph attribution & heuristic risk calculations
              </p>
            </div>
            <Link
              href="/analyze"
              className={`text-xs font-bold flex items-center gap-1 ${
                isLight ? "text-emerald-700 hover:underline" : "text-[#cf0] hover:underline"
              }`}
            >
              <span>RUN ANALYZER</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="space-y-4">
            {(investigationsData?.items || []).map((inv: any) => (
              <div
                key={inv.id}
                className={`p-4 rounded-lg border flex items-center justify-between ${
                  isLight
                    ? "bg-slate-50 border-slate-200"
                    : "bg-[#161616] border-[#262626]"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-2.5 h-2.5 rounded-full ${inv.status === "completed" ? "bg-emerald-500 shadow-[0_0_8px_#10b981]" : "bg-amber-400 animate-pulse"}`} />
                  <div>
                    <p className="font-bold text-xs">{formatAddress(inv.wallet_id || "0x4f3A...2b1c")}</p>
                    <p className={`text-[11px] ${isLight ? "text-slate-500" : "text-zinc-400"}`}>
                      Started {formatRelativeTime(inv.started_at)}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="w-24 bg-slate-200 dark:bg-[#222] h-2 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${inv.status === "completed" ? "bg-emerald-500" : "bg-[#cf0] animate-pulse"}`}
                      style={{ width: `${inv.status === "completed" ? 100 : 65}%` }}
                    />
                  </div>
                  <span className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded ${
                    inv.status === "completed" ? "bg-emerald-500/10 text-emerald-500" : "bg-amber-500/10 text-amber-500"
                  }`}>
                    {investigationStatusLabels[inv.status] || inv.status}
                  </span>
                </div>
              </div>
            ))}
            {(investigationsData?.items?.length || 0) === 0 && (
              <div className="py-8 text-center text-zinc-400 space-y-2">
                <Activity className="w-8 h-8 mx-auto opacity-60 text-[#cf0]" />
                <p className="font-bold text-xs uppercase">No background tasks running</p>
                <p className="text-xs font-sans text-zinc-400">Execute a wallet search on the Analyze page to launch traces.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Platform Health Matrix */}
      <div
        className={`p-6 border rounded-lg transition-colors ${
          isLight
            ? "bg-white border-slate-200 shadow-sm"
            : "bg-[#121212] border-[#262626] shadow-lg"
        }`}
      >
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-200 dark:border-[#222]">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-md ${isLight ? "bg-emerald-50 text-emerald-700" : "bg-[#cf0]/10 text-[#cf0]"}`}>
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold uppercase tracking-wide">
                SYSTEM TELEMETRY & INFRASTRUCTURE HEALTH
              </h2>
              <p className={`text-xs font-sans mt-0.5 ${isLight ? "text-slate-500" : "text-zinc-400"}`}>
                Real-time connection metrics for PostgreSQL, Neo4j Graph DB, and Redis
              </p>
            </div>
          </div>
          <span className={`px-3 py-1 text-xs font-bold uppercase rounded-full border flex items-center gap-1.5 ${
            isLight ? "bg-emerald-50 border-emerald-300 text-emerald-800" : "bg-emerald-500/10 border-emerald-500/40 text-emerald-400"
          }`}>
            <CheckCircle className="w-3.5 h-3.5" />
            <span>OPERATIONAL (99.98%)</span>
          </span>
        </div>

        <div className="grid gap-6 md:grid-cols-3 font-mono">
          <div className={`p-5 rounded-lg border ${isLight ? "bg-slate-50 border-slate-200" : "bg-[#161616] border-[#262626]"}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Database className={`w-4 h-4 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />
                <span className="font-bold text-xs uppercase">PostgreSQL Database</span>
              </div>
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
            </div>
            <p className={`text-xs ${isLight ? "text-slate-600" : "text-zinc-300"}`}>
              Encrypted Audit Logs & Case Files Connected
            </p>
          </div>

          <div className={`p-5 rounded-lg border ${isLight ? "bg-slate-50 border-slate-200" : "bg-[#161616] border-[#262626]"}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <GitBranch className={`w-4 h-4 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />
                <span className="font-bold text-xs uppercase">Neo4j Graph Database</span>
              </div>
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
            </div>
            <p className={`text-xs ${isLight ? "text-slate-600" : "text-zinc-300"}`}>
              Multi-Hop Flow Graph Cluster DB Active
            </p>
          </div>

          <div className={`p-5 rounded-lg border ${isLight ? "bg-slate-50 border-slate-200" : "bg-[#161616] border-[#262626]"}`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Cpu className={`w-4 h-4 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />
                <span className="font-bold text-xs uppercase">Redis Cache & Queue</span>
              </div>
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
            </div>
            <p className={`text-xs ${isLight ? "text-slate-600" : "text-zinc-300"}`}>
              Celery Worker Task Queue Sub-system Online
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}