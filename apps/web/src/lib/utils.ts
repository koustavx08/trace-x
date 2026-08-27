import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatAddress(address: string, chars = 6): string {
  if (!address) return "";
  if (address.length <= chars * 2) return address;
  return `${address.slice(0, chars)}...${address.slice(-chars)}`;
}

export function formatNumber(num: number | string): string {
  const n = typeof num === "string" ? parseFloat(num) : num;
  if (isNaN(n)) return "0";
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(2)}K`;
  return n.toLocaleString();
}

export function formatCurrency(value: number | string, currency = "USD"): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(n)) return `$0.00`;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

export function formatDate(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

export function formatRelativeTime(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(d);
}

export function getRiskColor(score: number): string {
  if (score >= 75) return "text-destructive";
  if (score >= 50) return "text-amber-400";
  if (score >= 25) return "text-yellow-400";
  return "text-green-400";
}

export function getRiskBg(score: number): string {
  if (score >= 75) return "bg-destructive/10 border-destructive/20";
  if (score >= 50) return "bg-amber-400/10 border-amber-400/20";
  if (score >= 25) return "bg-yellow-400/10 border-yellow-400/20";
  return "bg-green-400/10 border-green-400/20";
}

export function getConfidenceColor(confidence: string): string {
  switch (confidence) {
    case "CONFIRMED":
      return "text-green-400 bg-green-400/10 border-green-400/20";
    case "HIGH_CONFIDENCE":
      return "text-blue-400 bg-blue-400/10 border-blue-400/20";
    case "PROBABLE":
      return "text-amber-400 bg-amber-400/10 border-amber-400/20";
    default:
      return "text-muted-foreground bg-muted border-border";
  }
}

export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  ms: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), ms);
  };
}