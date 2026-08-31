import { Shield } from "lucide-react";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-tracex-dark px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary">
            <Shield className="h-7 w-7 text-primary-foreground" />
          </div>
          <span className="text-xl font-semibold text-foreground">TRACE-X</span>
          <p className="text-sm text-muted-foreground text-center">
            Real-Time Cryptocurrency Fraud Attribution &amp; Investigation Platform
          </p>
        </div>
        <div className="rounded-lg border border-tracex-border bg-tracex-surface p-6 shadow-sm">
          {children}
        </div>
      </div>
    </div>
  );
}
