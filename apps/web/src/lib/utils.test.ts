import {
  cn,
  formatAddress,
  formatNumber,
  formatCurrency,
  formatDate,
  formatRelativeTime,
  getRiskColor,
  getRiskBg,
  getConfidenceColor,
  debounce,
} from "./utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("resolves conflicting tailwind classes with the last one winning", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });

  it("ignores falsy values", () => {
    expect(cn("a", false, undefined, null, "b")).toBe("a b");
  });
});

describe("formatAddress", () => {
  it("returns empty string for empty input", () => {
    expect(formatAddress("")).toBe("");
  });

  it("returns the address unchanged when shorter than 2x chars", () => {
    expect(formatAddress("0x1234", 6)).toBe("0x1234");
  });

  it("truncates a long address with default chars", () => {
    const address = "0x1234567890abcdef1234567890abcdef12345678";
    expect(formatAddress(address)).toBe("0x1234...345678");
  });

  it("respects a custom chars length", () => {
    const address = "0x1234567890abcdef1234567890abcdef12345678";
    expect(formatAddress(address, 4)).toBe("0x12...5678");
  });
});

describe("formatNumber", () => {
  it("returns 0 for NaN input", () => {
    expect(formatNumber("not-a-number")).toBe("0");
  });

  it("formats billions", () => {
    expect(formatNumber(2_500_000_000)).toBe("2.50B");
  });

  it("formats millions", () => {
    expect(formatNumber(1_500_000)).toBe("1.50M");
  });

  it("formats thousands", () => {
    expect(formatNumber(1500)).toBe("1.50K");
  });

  it("formats small numbers with locale formatting", () => {
    expect(formatNumber(42)).toBe((42).toLocaleString());
  });

  it("accepts numeric strings", () => {
    expect(formatNumber("1000")).toBe("1.00K");
  });
});

describe("formatCurrency", () => {
  it("returns $0.00 for NaN input", () => {
    expect(formatCurrency("nope")).toBe("$0.00");
  });

  it("formats a numeric value as USD currency", () => {
    expect(formatCurrency(1234.5)).toBe("$1,234.50");
  });

  it("accepts numeric strings", () => {
    expect(formatCurrency("10")).toBe("$10.00");
  });
});

describe("formatDate", () => {
  it("formats a date string", () => {
    const result = formatDate("2024-01-15T10:30:00Z");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("formats a Date instance", () => {
    const result = formatDate(new Date("2024-01-15T10:30:00Z"));
    expect(typeof result).toBe("string");
  });
});

describe("formatRelativeTime", () => {
  it("returns 'just now' for very recent timestamps", () => {
    expect(formatRelativeTime(new Date())).toBe("just now");
  });

  it("returns minutes-ago for timestamps within the hour", () => {
    const date = new Date(Date.now() - 5 * 60 * 1000);
    expect(formatRelativeTime(date)).toBe("5m ago");
  });

  it("returns hours-ago for timestamps within the day", () => {
    const date = new Date(Date.now() - 3 * 60 * 60 * 1000);
    expect(formatRelativeTime(date)).toBe("3h ago");
  });

  it("falls back to a formatted date for old timestamps", () => {
    const date = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
    const result = formatRelativeTime(date);
    expect(result).not.toMatch(/ago$/);
  });
});

describe("getRiskColor", () => {
  it("returns destructive color for high risk", () => {
    expect(getRiskColor(80)).toBe("text-destructive");
  });

  it("returns amber for medium-high risk", () => {
    expect(getRiskColor(60)).toBe("text-amber-400");
  });

  it("returns yellow for medium-low risk", () => {
    expect(getRiskColor(30)).toBe("text-yellow-400");
  });

  it("returns green for low risk", () => {
    expect(getRiskColor(10)).toBe("text-green-400");
  });
});

describe("getRiskBg", () => {
  it("returns destructive background for high risk", () => {
    expect(getRiskBg(90)).toContain("bg-destructive/10");
  });

  it("returns green background for low risk", () => {
    expect(getRiskBg(0)).toContain("bg-green-400/10");
  });
});

describe("getConfidenceColor", () => {
  it("returns green styling for CONFIRMED", () => {
    expect(getConfidenceColor("CONFIRMED")).toContain("text-green-400");
  });

  it("returns blue styling for HIGH_CONFIDENCE", () => {
    expect(getConfidenceColor("HIGH_CONFIDENCE")).toContain("text-blue-400");
  });

  it("returns amber styling for PROBABLE", () => {
    expect(getConfidenceColor("PROBABLE")).toContain("text-amber-400");
  });

  it("returns default styling for unknown confidence", () => {
    expect(getConfidenceColor("UNKNOWN")).toContain("text-muted-foreground");
  });
});

describe("debounce", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("only invokes the function once after the delay when called repeatedly", () => {
    const fn = jest.fn();
    const debounced = debounce(fn, 200);

    debounced();
    debounced();
    debounced();

    expect(fn).not.toHaveBeenCalled();

    jest.advanceTimersByTime(200);

    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("passes through the latest arguments", () => {
    const fn = jest.fn();
    const debounced = debounce(fn, 100);

    debounced("first");
    debounced("second");

    jest.advanceTimersByTime(100);

    expect(fn).toHaveBeenCalledWith("second");
  });
});
