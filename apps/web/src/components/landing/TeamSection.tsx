"use client";

import { Shield, Cpu, Code2, Scale, Terminal, Users } from "lucide-react";
import { useLandingTheme } from "@/lib/theme-context";

const teamPillars = [
  {
    id: "01",
    role: "BLOCKCHAIN FORENSICS",
    title: "Graph Tracing & VASP Attribution",
    desc: "Engineered high-performance recursive fund flow algorithms, Dijkstra shortest-path entity attribution, and EIP-55 multi-chain address parsers.",
    icon: (isLight: boolean) => <Shield className={`w-6 h-6 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />,
    tags: ["Graph Analysis", "VASP Attribution", "On-Chain RPC"],
  },
  {
    id: "02",
    role: "AI & MACHINE LEARNING",
    title: "Attribution AI & Risk Scoring",
    desc: "Developed the 12-factor explainable threat evaluation model and evidence-grounded LLM synthesis for automated fraud investigation reports.",
    icon: (isLight: boolean) => <Cpu className={`w-6 h-6 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />,
    tags: ["12-Factor Risk Engine", "GNN Pattern Detection", "LLM Assistant"],
  },
  {
    id: "03",
    role: "FULL-STACK INFRASTRUCTURE",
    title: "High-Speed Platform & Visualization",
    desc: "Built the reactive Next.js front-end, interactive React Flow graph visualizer, FastAPI back-end services, and multi-container Docker setup.",
    icon: (isLight: boolean) => <Code2 className={`w-6 h-6 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />,
    tags: ["Next.js 14", "React Flow", "FastAPI", "Neo4j"],
  },
  {
    id: "04",
    role: "COMPLIANCE & LEGAL FORENSICS",
    title: "Court-Ready Evidence Packaging",
    desc: "Designed standardized audit trails, chain-of-custody verification rules, and automated court-admissible PDF/HTML report generators.",
    icon: (isLight: boolean) => <Scale className={`w-6 h-6 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />,
    tags: ["Court-Ready PDF", "Chain of Custody", "Regulatory Standards"],
  },
];

export default function TeamSection() {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";

  return (
    <section
      id="team"
      className={`relative border-b px-6 md:px-16 py-28 transition-colors duration-300 ${
        isLight
          ? "bg-white border-slate-200 text-slate-900"
          : "bg-[#090909] border-[#262626] text-white"
      }`}
    >
      <div className="max-w-7xl mx-auto relative">
        {/* Telemetry Marker */}
        <div
          className={`text-xs font-mono font-bold absolute -top-16 left-0 tracking-wider ${
            isLight ? "text-emerald-700" : "text-[#cf0]"
          }`}
        >
          /03_TEAM_SPECS
        </div>

        {/* Section Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-16">
          <div className="space-y-3">
            <div
              className={`inline-flex items-center gap-2 px-3 py-1.5 font-mono text-xs uppercase font-extrabold rounded-full border shadow-sm ${
                isLight
                  ? "bg-emerald-50 border-emerald-300 text-emerald-800"
                  : "bg-[#cf0]/10 border-[#cf0]/40 text-[#cf0]"
              }`}
            >
              <Users className="w-4 h-4" />
              <span>SIH 2026 ARCHITECTS</span>
            </div>
            <h2 className="text-3xl md:text-5xl font-mono uppercase font-black tracking-tight">
              ABOUT THE{" "}
              <span className={isLight ? "text-emerald-700" : "text-[#cf0]"}>
                TEAM
              </span>
            </h2>
          </div>

          <p
            className={`font-sans text-sm md:text-base max-w-md leading-relaxed ${
              isLight ? "text-slate-700 font-medium" : "text-zinc-300 font-normal"
            }`}
          >
            We are dedicated engineers and researchers building Next-Gen crypto crime attribution technology for law enforcement, exchanges, and security analysts.
          </p>
        </div>

        {/* Team Pillars Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-16">
          {teamPillars.map((member) => (
            <div
              key={member.id}
              className={`p-8 flex flex-col justify-between gap-6 transition-all duration-300 group relative overflow-hidden border rounded-lg ${
                isLight
                  ? "bg-slate-50/70 border-slate-200 hover:border-slate-900 shadow-sm hover:shadow-md"
                  : "bg-[#121212] border-[#262626] hover:border-[#cf0]/70 shadow-lg"
              }`}
            >
              {/* Corner Accent */}
              <div
                className={`absolute top-0 right-0 size-8 border-t border-r transition-colors ${
                  isLight
                    ? "border-slate-300 group-hover:border-slate-900"
                    : "border-[#333] group-hover:border-[#cf0]"
                }`}
              />

              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <div
                    className={`size-14 border rounded-md flex items-center justify-center transition-colors shrink-0 ${
                      isLight
                        ? "bg-white border-slate-300 group-hover:border-slate-900"
                        : "bg-[#18181c] border-[#333] group-hover:border-[#cf0]"
                    }`}
                  >
                    {member.icon(isLight)}
                  </div>
                  <div>
                    <span
                      className={`font-mono text-xs font-bold uppercase tracking-wider block ${
                        isLight ? "text-emerald-700" : "text-[#cf0]"
                      }`}
                    >
                      {member.role}
                    </span>
                    <h3
                      className={`font-mono text-lg font-bold transition-colors mt-1 ${
                        isLight ? "text-slate-900 group-hover:text-emerald-700" : "text-white group-hover:text-[#cf0]"
                      }`}
                    >
                      {member.title}
                    </h3>
                  </div>
                </div>
                <span
                  className={`font-mono text-xs font-bold ${
                    isLight ? "text-slate-400" : "text-zinc-500"
                  }`}
                >
                  PIL_0{member.id}
                </span>
              </div>

              {/* High-Contrast Description */}
              <p
                className={`font-sans text-sm md:text-base leading-relaxed ${
                  isLight ? "text-slate-700 font-medium" : "text-zinc-200 font-normal"
                }`}
              >
                {member.desc}
              </p>

              <div
                className={`flex flex-wrap gap-2 pt-3 border-t ${
                  isLight ? "border-slate-200" : "border-[#222]"
                }`}
              >
                {member.tags.map((tag) => (
                  <span
                    key={tag}
                    className={`px-3 py-1 border font-mono text-xs font-semibold rounded-sm ${
                      isLight
                        ? "bg-white border-slate-300 text-slate-800"
                        : "bg-[#18181b] border-[#3f3f46] text-zinc-200"
                    }`}
                  >
                    #{tag}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Mission Statement Box */}
        <div
          className={`p-8 rounded-lg flex flex-col md:flex-row items-center justify-between gap-6 relative border ${
            isLight
              ? "bg-slate-50 border-emerald-500/50 shadow-sm"
              : "bg-[#121212] border-[#cf0]/40 shadow-xl"
          }`}
        >
          <div className="flex items-center gap-4">
            <div
              className={`size-12 rounded-md border flex items-center justify-center shrink-0 ${
                isLight
                  ? "bg-emerald-100 border-emerald-400 text-emerald-800"
                  : "bg-[#cf0]/10 border-[#cf0] text-[#cf0]"
              }`}
            >
              <Terminal className="w-6 h-6" />
            </div>
            <div>
              <h4 className="font-mono text-base font-extrabold uppercase tracking-wide">
                TRACE-X MISSION STATEMENT
              </h4>
              <p
                className={`font-sans text-sm md:text-base leading-relaxed mt-1 ${
                  isLight ? "text-slate-700 font-medium" : "text-zinc-200 font-normal"
                }`}
              >
                Transforming days of manual blockchain exploration into seconds of automated, court-ready attribution. Zero compromise.
              </p>
            </div>
          </div>

          <div
            className={`shrink-0 px-5 py-2.5 rounded-full border font-mono text-xs uppercase font-extrabold tracking-wider ${
              isLight
                ? "bg-emerald-50 border-emerald-400 text-emerald-900 shadow-sm"
                : "bg-[rgba(204,255,0,0.1)] border-[rgba(204,255,0,0.4)] text-[#cf0]"
            }`}
          >
            SIH 2026 PROTOTYPE READY
          </div>
        </div>
      </div>
    </section>
  );
}
