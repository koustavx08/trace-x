"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight, Terminal, ShieldAlert, Sparkles, Activity } from "lucide-react";
import { useLandingTheme } from "@/lib/theme-context";

function LeftEdge({ isLight }: { isLight: boolean }) {
  return (
    <div className="absolute bottom-0 left-px top-0 w-[36px] hidden md:block z-10">
      <div
        aria-hidden
        className={`absolute border-r border-solid inset-0 pointer-events-none ${
          isLight ? "border-slate-200" : "border-[#2a2a2a]"
        }`}
      />
      <div className="flex flex-col items-center pb-6 pr-px pt-20 size-full relative">
        <div className="mb-[-81px] relative shrink-0 w-[32px]">
          <div className="flex flex-col items-center pl-[8px] pr-[9px] relative size-full">
            <div className="flex h-[177px] items-center justify-center relative shrink-0 w-[15px]">
              <div className="-rotate-90 flex-none">
                <div
                  className={`flex gap-[8px] items-start text-xs tracking-[2px] uppercase font-mono font-semibold whitespace-nowrap ${
                    isLight ? "text-slate-500" : "text-[#a1a1aa]"
                  }`}
                >
                  <span>2026</span>
                  <span>|</span>
                  <span>CRYPTO FRAUD FORENSICS</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="flex-1 flex flex-col justify-end pb-8">
          <div className="flex flex-col gap-[6px] items-start">
            <div
              className={`size-[5px] rounded-full ${
                isLight ? "bg-emerald-600 shadow-[0_0_8px_#10b981]" : "bg-[#cf0] shadow-[0_0_10px_#cf0]"
              }`}
            />
            <div className={isLight ? "bg-slate-300 size-[4px] rounded-full" : "bg-[#52525b] size-[4px] rounded-full"} />
            <div className={isLight ? "bg-slate-300 size-[4px] rounded-full" : "bg-[#52525b] size-[4px] rounded-full"} />
            <div className={isLight ? "bg-slate-300 size-[4px] rounded-full" : "bg-[#52525b] size-[4px] rounded-full"} />
          </div>
        </div>
      </div>
    </div>
  );
}

function RightEdge({ isLight }: { isLight: boolean }) {
  return (
    <div className="absolute bottom-0 right-[2px] top-0 w-[32px] hidden md:block z-10">
      <div
        aria-hidden
        className={`absolute border-l border-solid inset-0 pointer-events-none ${
          isLight ? "border-slate-200" : "border-[#2a2a2a]"
        }`}
      />
      <div className="flex flex-col items-center pl-px py-6 relative size-full opacity-60">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex flex-col items-start w-full mb-4">
            <span
              className={`text-sm leading-[16px] font-mono font-bold ${
                isLight ? "text-slate-400" : "text-zinc-600"
              }`}
            >
              +
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HeroSection() {
  const { theme } = useLandingTheme();
  const isLight = theme === "light";

  return (
    <section
      id="investigate"
      className={`relative border-b overflow-hidden transition-colors duration-300 ${
        isLight
          ? "bg-gradient-to-b from-slate-50 via-white to-slate-50 border-slate-200 text-slate-900"
          : "bg-gradient-to-b from-[#0a0a0a] via-[#0d0d0d] to-[#0a0a0a] border-[#262626] text-white"
      }`}
    >
      <LeftEdge isLight={isLight} />
      <RightEdge isLight={isLight} />

      {/* Background Subtle Glow Grid */}
      <div
        className={`absolute inset-0 pointer-events-none opacity-20 ${
          isLight
            ? "bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] [background-size:24px_24px]"
            : "bg-[radial-gradient(#27272a_1px,transparent_1px)] [background-size:24px_24px]"
        }`}
      />

      {/* Telemetry Markers */}
      <div
        className={`text-xs font-mono font-bold absolute left-4 md:left-14 top-20 -translate-y-1/2 tracking-wider ${
          isLight ? "text-emerald-700" : "text-[#cf0]"
        }`}
      >
        /01_INVESTIGATE
      </div>
      <div
        className={`text-xs font-mono font-semibold absolute bottom-4 right-6 hidden md:block tracking-widest ${
          isLight ? "text-slate-500" : "text-zinc-500"
        }`}
      >
        {"//SCN_01_ACTIVE"}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 px-6 md:px-16 pt-28 pb-24 max-w-7xl mx-auto min-h-[720px] relative z-10">
        {/* Text Block */}
        <div className="flex flex-col justify-center gap-8">
          <div className="flex items-center gap-3">
            <span
              className={`px-3 py-1.5 rounded-full font-mono text-xs tracking-wider uppercase font-bold border flex items-center gap-2 shadow-sm ${
                isLight
                  ? "bg-emerald-50 border-emerald-300 text-emerald-800"
                  : "bg-[rgba(204,255,0,0.1)] border-[#cf0]/40 text-[#cf0] shadow-[0_0_15px_rgba(204,255,0,0.1)]"
              }`}
            >
              <Activity className="w-3.5 h-3.5 animate-pulse" />
              <span>REAL-TIME ON-CHAIN FORENSICS</span>
            </span>
          </div>

          <div className="flex flex-col gap-3">
            <h1
              className={`text-xl md:text-2xl tracking-[3px] uppercase font-extrabold font-mono ${
                isLight ? "text-slate-900" : "text-[#cf0]"
              }`}
            >
              TRACE-X PLATFORM
            </h1>
            <p
              className={`text-4xl md:text-6xl font-mono-share leading-[1.1] uppercase font-black tracking-tight ${
                isLight ? "text-slate-900" : "text-white"
              }`}
            >
              THE FRAUD ISN&apos;T HIDDEN.
              <br />
              <span className={isLight ? "text-emerald-600" : "text-[#cf0]"}>
                IT LEAVES TRACES.
              </span>
            </p>
          </div>

          {/* High-Contrast Enhanced Description */}
          <p
            className={`text-base md:text-xl max-w-xl leading-relaxed font-sans font-normal ${
              isLight ? "text-slate-700 font-medium" : "text-zinc-200"
            }`}
          >
            We surface crypto scams, wallet exploits, mixer loops, and on-chain deception before they claim another victim. Raw blockchain data. Systematic AI attribution. Zero compromise.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <Link
              href="/login"
              className={`font-mono font-extrabold text-sm tracking-wider px-8 py-4 flex items-center gap-3 transition-all duration-300 transform hover:scale-[1.02] active:scale-[0.98] ${
                isLight
                  ? "bg-slate-900 hover:bg-slate-800 text-white shadow-lg"
                  : "bg-[#cf0] hover:bg-[#b8e000] text-black shadow-[0_0_25px_rgba(204,255,0,0.3)]"
              }`}
            >
              <span>LAUNCH APP</span>
              <ArrowUpRight className={`w-4 h-4 ${isLight ? "text-white" : "text-black"}`} />
            </Link>

            <a
              href="#team"
              className={`relative flex items-center gap-3 px-7 py-4 border font-mono font-bold text-sm tracking-wider transition-all duration-200 ${
                isLight
                  ? "bg-white border-slate-300 text-slate-900 hover:border-slate-900 hover:bg-slate-50 shadow-sm"
                  : "bg-[#141414] border-[#333] text-white hover:border-[#cf0] hover:bg-[#1a1a1a]"
              }`}
            >
              <ShieldAlert className={`w-4 h-4 ${isLight ? "text-emerald-700" : "text-[#cf0]"}`} />
              <span>ABOUT THE TEAM</span>
            </a>
          </div>

          {/* Key Metrics Ticker with High Contrast */}
          <div
            className={`grid grid-cols-3 gap-6 pt-6 border-t ${
              isLight ? "border-slate-200" : "border-[#262626]"
            }`}
          >
            <div className="space-y-1">
              <p className={`text-2xl md:text-3xl font-mono font-black ${isLight ? "text-emerald-700" : "text-[#cf0]"}`}>
                $142M+
              </p>
              <p className={`text-xs md:text-sm font-mono font-semibold ${isLight ? "text-slate-600" : "text-zinc-400"}`}>
                Stolen Tracked
              </p>
            </div>
            <div className="space-y-1">
              <p className={`text-2xl md:text-3xl font-mono font-black ${isLight ? "text-emerald-700" : "text-[#cf0]"}`}>
                38.4K+
              </p>
              <p className={`text-xs md:text-sm font-mono font-semibold ${isLight ? "text-slate-600" : "text-zinc-400"}`}>
                Wallets Flagged
              </p>
            </div>
            <div className="space-y-1">
              <p className={`text-2xl md:text-3xl font-mono font-black ${isLight ? "text-emerald-700" : "text-[#cf0]"}`}>
                &lt; 1.2s
              </p>
              <p className={`text-xs md:text-sm font-mono font-semibold ${isLight ? "text-slate-600" : "text-zinc-400"}`}>
                AI Trace Speed
              </p>
            </div>
          </div>
        </div>

        {/* Visual Wireframe Block */}
        <div
          className={`relative flex items-center justify-center min-h-[480px] lg:h-[560px] border group overflow-hidden transition-all duration-300 rounded-lg ${
            isLight
              ? "bg-white border-slate-200 shadow-2xl"
              : "bg-[#0d0d0d] border-[#2a2a2a] shadow-[0_0_40px_rgba(0,0,0,0.8)]"
          }`}
        >
          {/* Scanning Telemetry Corner Overlays */}
          <div className="absolute top-4 left-4 z-20 flex items-center gap-2.5">
            <Terminal className={`w-4 h-4 animate-pulse ${isLight ? "text-emerald-600" : "text-[#cf0]"}`} />
            <div className={`text-xs font-mono-share leading-tight ${isLight ? "text-slate-900 font-bold" : "text-[#cf0]"}`}>
              <p className="font-bold tracking-wide">SCANNER ACTIVE</p>
              <p className={isLight ? "text-slate-600 font-medium" : "text-zinc-300"}>MODEL: TRACE-AI-v4.2</p>
            </div>
          </div>

          <div
            className={`absolute top-4 right-4 size-[14px] border-t-2 border-r-2 ${
              isLight ? "border-emerald-600" : "border-[#cf0]"
            }`}
          />
          <div
            className={`absolute bottom-4 left-4 size-[14px] border-b-2 border-l-2 ${
              isLight ? "border-emerald-600" : "border-[#cf0]"
            }`}
          />
          <div
            className={`absolute bottom-4 right-4 size-[14px] border-b-2 border-r-2 ${
              isLight ? "border-emerald-600" : "border-[#cf0]"
            }`}
          />

          {/* Main 3D Graphics Render */}
          <div className="relative w-full h-full mix-blend-luminosity opacity-90 overflow-hidden flex items-center justify-center p-2">
            <Image
              src="/landing/3f71d763df0fa16eb87d630ad698968ce0db6d87.png"
              alt="TRACE-X 3D Cyber Wireframe Render"
              fill
              className="object-cover transition-transform duration-700 group-hover:scale-105"
              priority
            />
            <div
              className={`absolute inset-0 mix-blend-multiply ${
                isLight ? "bg-slate-100/10" : "bg-[#0a0a0a]/20"
              }`}
            />
          </div>

          {/* Real-Time Scan Radar Line */}
          <div
            className={`absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-[#cf0] to-transparent shadow-[0_0_15px_#cf0] animate-pulse top-1/3 opacity-80`}
          />

          {/* Coordinates HUD Box with Crisp High Contrast */}
          <div
            className={`absolute bottom-6 right-6 backdrop-blur-md p-4 shadow-2xl z-20 border space-y-1.5 ${
              isLight
                ? "bg-white/95 border-emerald-500/50 text-slate-900 shadow-slate-300"
                : "bg-black/90 border-[#cf0]/60 text-white shadow-black"
            }`}
          >
            {[
              ["TARGET_WALLET", "0x4f3A...2b1c"],
              ["BLOCKCHAIN", "ETH_MAINNET"],
              ["RISK_SCORE", "CRITICAL (98.4%)"],
            ].map(([label, val]) => (
              <div
                key={label}
                className="text-xs font-mono-share flex items-center justify-between gap-6"
              >
                <span className={isLight ? "text-slate-600 font-semibold" : "text-zinc-400 font-medium"}>
                  {label}:
                </span>
                <span className={`font-bold ${isLight ? "text-slate-900" : "text-[#cf0]"}`}>
                  {val}
                </span>
              </div>
            ))}
          </div>

          {/* Glitch Accent Overlay */}
          <div
            className={`absolute h-3 mix-blend-difference right-8 top-12 w-20 pointer-events-none opacity-60 ${
              isLight ? "bg-emerald-500" : "bg-[#cf0]"
            }`}
          />
          <div
            className={`absolute bottom-16 left-16 mix-blend-difference size-6 pointer-events-none opacity-60 ${
              isLight ? "bg-emerald-500" : "bg-[#cf0]"
            }`}
          />
        </div>
      </div>
    </section>
  );
}
