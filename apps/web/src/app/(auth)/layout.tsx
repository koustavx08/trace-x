import { Shield } from "lucide-react";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F5F7FA] px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#3430D9] shadow-sm">
            <Shield className="h-7 w-7 text-white" />
          </div>
          <span className="text-2xl font-bold text-[#151B2B] tracking-tight">TRACE-X</span>
          <p className="text-xs text-[#73798D] text-center font-normal">
            Real-Time Cryptocurrency Fraud Attribution &amp; Investigation Platform
          </p>
        </div>
        <div className="rounded-2xl border border-[#E5E7EB] bg-white p-8 shadow-sm">
          {children}
        </div>
      </div>
    </div>
  );
}
