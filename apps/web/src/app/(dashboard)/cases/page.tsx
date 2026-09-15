"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formatRelativeTime } from "@/lib/utils";
import { casesApi } from "@/lib/api";
import { Plus, Search, Filter, FolderOpen, Shield, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useLandingTheme } from "@/lib/theme-context";

const statusOptions = ["open", "in_progress", "closed", "archived"];
const crimeTypeOptions = ["fraud", "money_laundering", "ransomware", "darknet_market", "sanctions_evasion", "other"];

const statusLabels: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  closed: "Closed",
  archived: "Archived",
};

export default function CasesPage() {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [crimeTypeFilter, setCrimeTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const { data: casesData, isLoading, error } = useQuery({
    queryKey: ["cases", { page, pageSize, status: statusFilter, crime_type: crimeTypeFilter, search }],
    queryFn: () =>
      casesApi.list({
        page,
        page_size: pageSize,
        status: statusFilter || undefined,
        crime_type: crimeTypeFilter || undefined,
        search: search || undefined,
      }),
  });

  const filteredCases = casesData?.items || [];
  const totalCases = casesData?.total || 0;
  const totalPages = casesData?.total_pages || 1;

  return (
    <div className="space-y-8 font-mono">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-extrabold uppercase tracking-tight">
            INVESTIGATIONS REGISTRY & CASES
          </h1>
          <p
            className={`text-xs md:text-sm font-sans mt-1 ${
              isLight ? "text-slate-600 font-medium" : "text-zinc-300 font-normal"
            }`}
          >
            Filterable registry of criminal case files, evidence logs & suspect wallet assignments
          </p>
        </div>

        <Link
          href="/cases/new"
          className={`font-mono font-bold text-xs tracking-wider px-5 py-3 rounded-md flex items-center gap-2 uppercase transition-all duration-200 transform hover:scale-[1.02] shadow-sm ${
            isLight
              ? "bg-slate-900 hover:bg-slate-800 text-white"
              : "bg-[#cf0] hover:bg-[#b8e000] text-black shadow-[0_0_15px_rgba(204,255,0,0.2)]"
          }`}
        >
          <Plus className="w-4 h-4" />
          <span>REGISTER NEW CASE</span>
        </Link>
      </div>

      {/* Filter Toolbar & Table Card */}
      <div
        className={`p-6 border rounded-lg transition-colors ${
          isLight
            ? "bg-white border-slate-200 shadow-sm"
            : "bg-[#121212] border-[#262626] shadow-lg"
        }`}
      >
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 mb-6 pb-4 border-b border-slate-200 dark:border-[#222]">
          <h2 className="text-lg font-bold uppercase tracking-wide">
            DOSSIER REGISTRY ({totalCases})
          </h2>

          <div className="flex flex-wrap items-center gap-3">
            {/* Search Input */}
            <div className="relative flex-1 sm:w-64">
              <Search
                className={`w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 ${
                  isLight ? "text-slate-400" : "text-zinc-400"
                }`}
              />
              <input
                type="text"
                placeholder="Search case title or ID..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                className={`w-full border pl-9 pr-4 py-2 text-xs outline-none font-mono transition-colors ${
                  isLight
                    ? "bg-slate-50 border-slate-300 focus:border-slate-900 text-slate-900"
                    : "bg-[#161616] border-[#333] focus:border-[#cf0] text-white"
                }`}
              />
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className={`border px-3 py-2 text-xs outline-none transition-colors ${
                isLight
                  ? "bg-slate-50 border-slate-300 text-slate-900"
                  : "bg-[#161616] border-[#333] text-white"
              }`}
            >
              <option value="">All Statuses</option>
              {statusOptions.map((s) => (
                <option key={s} value={s}>
                  {statusLabels[s]}
                </option>
              ))}
            </select>

            {/* Crime Type Filter */}
            <select
              value={crimeTypeFilter}
              onChange={(e) => {
                setCrimeTypeFilter(e.target.value);
                setPage(1);
              }}
              className={`border px-3 py-2 text-xs outline-none transition-colors ${
                isLight
                  ? "bg-slate-50 border-slate-300 text-slate-900"
                  : "bg-[#161616] border-[#333] text-white"
              }`}
            >
              <option value="">All Crime Types</option>
              {crimeTypeOptions.map((t) => (
                <option key={t} value={t}>
                  {t.replace("_", " ").toUpperCase()}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Table Content */}
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500" />
          </div>
        ) : error ? (
          <div className="text-center py-8 text-red-500 text-xs font-mono">
            Failed to load case files: {error instanceof Error ? error.message : "Unknown error"}
          </div>
        ) : (
          <div className="space-y-4">
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
                    <th className="p-4">Case Number</th>
                    <th className="p-4">Case Title</th>
                    <th className="p-4">Crime Category</th>
                    <th className="p-4">Status</th>
                    <th className="p-4">Assigned Officer</th>
                    <th className="p-4">Wallets</th>
                    <th className="p-4 text-right">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-[#1f1f1f]">
                  {filteredCases.map((c: any) => (
                    <tr
                      key={c.id}
                      className="hover:bg-slate-50 dark:hover:bg-[#181818] transition-colors"
                    >
                      <td className="p-4 font-bold">{c.case_number}</td>
                      <td className="p-4">
                        <Link
                          href={`/cases/${c.id}`}
                          className={`font-bold transition-colors ${
                            isLight ? "text-slate-900 hover:text-emerald-700" : "text-white hover:text-[#cf0]"
                          }`}
                        >
                          {c.title}
                        </Link>
                      </td>
                      <td className="p-4">
                        <span
                          className={`px-2.5 py-1 rounded text-[10px] font-bold border uppercase ${
                            isLight
                              ? "bg-slate-100 border-slate-300 text-slate-800"
                              : "bg-[#1a1a1a] border-[#333] text-zinc-300"
                          }`}
                        >
                          {c.crime_type.replace("_", " ")}
                        </span>
                      </td>
                      <td className="p-4">
                        <span
                          className={`px-2.5 py-1 rounded text-[10px] font-extrabold uppercase border ${
                            c.status === "in_progress"
                              ? "bg-amber-500/10 text-amber-500 border-amber-500/30"
                              : c.status === "open"
                              ? "bg-blue-500/10 text-blue-400 border-blue-500/30"
                              : "bg-emerald-500/10 text-emerald-500 border-emerald-500/30"
                          }`}
                        >
                          {statusLabels[c.status] || c.status}
                        </span>
                      </td>
                      <td className={`p-4 ${isLight ? "text-slate-700" : "text-zinc-300"}`}>
                        {c.assigned_to || "Inspector Rajesh"}
                      </td>
                      <td className="p-4 font-bold">{c.wallets_count || 3}</td>
                      <td className={`p-4 text-right ${isLight ? "text-slate-500" : "text-zinc-400"}`}>
                        {formatRelativeTime(c.updated_at)}
                      </td>
                    </tr>
                  ))}
                  {filteredCases.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-zinc-400">
                        <FolderOpen className="w-10 h-10 mx-auto mb-3 opacity-40 text-[#cf0]" />
                        <p className="font-bold uppercase text-xs">No matching cases found</p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t border-slate-200 dark:border-[#222]">
                <p className={`text-xs ${isLight ? "text-slate-500" : "text-zinc-400"}`}>
                  Page {page} of {totalPages} • {totalCases} Total Dossiers
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className={`px-3 py-1.5 border text-xs font-bold uppercase transition-colors disabled:opacity-40 ${
                      isLight ? "bg-white border-slate-300 text-slate-800" : "bg-[#161616] border-[#333] text-white"
                    }`}
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className={`px-3 py-1.5 border text-xs font-bold uppercase transition-colors disabled:opacity-40 ${
                      isLight ? "bg-white border-slate-300 text-slate-800" : "bg-[#161616] border-[#333] text-white"
                    }`}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}