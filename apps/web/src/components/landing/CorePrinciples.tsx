"use client";

import { Link2, LayoutGrid, FileCheck, Scale } from "lucide-react";
import { useLandingTheme } from "@/lib/theme-context";

const principles = [
  {
    id: "01",
    label: "CHAIN",
    sublabel: "ANALYSIS",
    desc: ["On-chain data.", "Every transaction.", "Nothing hidden."],
    icon: (isLight: boolean) => <Link2 className={`w-6 h-6 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />,
  },
  {
    id: "02",
    label: "PATTERN",
    sublabel: "DETECTION",
    desc: ["Clusters. Flows.", "Mixers. Everything", "is connected."],
    icon: (isLight: boolean) => <LayoutGrid className={`w-6 h-6 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />,
  },
  {
    id: "03",
    label: "EVIDENCE",
    sublabel: "REPORTS",
    desc: ["Court-ready docs.", "Wallet maps and", "tx forensics."],
    icon: (isLight: boolean) => <FileCheck className={`w-6 h-6 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />,
  },
  {
    id: "04",
    label: "ZERO",
    sublabel: "COMPROMISE",
    desc: ["No bias.", "No pay-to-clear.", "No corruption."],
    icon: (isLight: boolean) => <Scale className={`w-6 h-6 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />,
  },
];

export default function CorePrinciples() {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";

  return (
    <section
      id="how-it-works"
      className={`relative border-b px-6 md:px-16 py-24 transition-colors duration-300 ${
        isLight
          ? "bg-slate-50/50 border-slate-200 text-slate-900"
          : "bg-[#0b0b0b] border-[#262626] text-white"
      }`}
    >
      <div className="max-w-7xl mx-auto relative">
        {/* Telemetry Marker */}
        <div
          className={`text-xs font-mono font-bold absolute -top-14 left-0 tracking-wider ${
            isLight ? "text-emerald-700" : "text-[#cf0]"
          }`}
        >
          /02_HOW_IT_WORKS
        </div>

        <div className="flex flex-col gap-3 mb-14">
          <p
            className={`text-xs font-mono font-bold tracking-[2.5px] uppercase ${
              isLight ? "text-emerald-700" : "text-[#cf0]"
            }`}
          >
            SYSTEM ARCHITECTURE
          </p>
          <h2 className="text-3xl md:text-4xl font-mono uppercase font-black tracking-tight">
            OUR CORE FORENSIC PRINCIPLES
          </h2>
          <p
            className={`text-sm md:text-base font-sans max-w-xl ${
              isLight ? "text-slate-600 font-medium" : "text-zinc-300 font-normal"
            }`}
          >
            Built from the ground up for total legal defensibility, high-speed graph analytics, and zero-compromise evidence attribution.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {principles.map((p) => (
            <div
              key={p.id}
              className={`p-7 flex flex-col justify-between transition-all duration-300 group border rounded-lg ${
                isLight
                  ? "bg-white border-slate-200 hover:border-slate-900 shadow-sm hover:shadow-md"
                  : "bg-[#121212] border-[#262626] hover:border-[#cf0]/60 shadow-lg"
              }`}
            >
              <div className="flex items-center justify-between mb-8">
                <div
                  className={`size-14 border rounded-md flex items-center justify-center transition-colors ${
                    isLight
                      ? "border-slate-300 bg-slate-50 group-hover:border-slate-900"
                      : "border-[#333] group-hover:border-[#cf0] bg-[#1a1a1a]"
                  }`}
                >
                  {p.icon(isLight)}
                </div>
                <span
                  className={`font-mono text-xs font-bold transition-colors ${
                    isLight ? "text-slate-500 group-hover:text-slate-900" : "text-zinc-500 group-hover:text-[#cf0]"
                  }`}
                >
                  P_{p.id}
                </span>
              </div>

              <div className="flex flex-col gap-3">
                <div
                  className={`text-lg font-bold font-mono tracking-wider transition-colors uppercase leading-tight ${
                    isLight ? "text-slate-900 group-hover:text-emerald-700" : "text-white group-hover:text-[#cf0]"
                  }`}
                >
                  <p>{p.label}</p>
                  <p>{p.sublabel}</p>
                </div>

                {/* High-Contrast Description */}
                <div
                  className={`text-sm font-sans space-y-1 ${
                    isLight ? "text-slate-700 font-medium" : "text-zinc-300 font-normal"
                  }`}
                >
                  {p.desc.map((line, i) => (
                    <p key={i} className="leading-relaxed">
                      {line}
                    </p>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
