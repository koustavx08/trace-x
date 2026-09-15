import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "./page";

jest.mock("@/lib/api", () => ({
  casesApi: { list: jest.fn(() => Promise.resolve({ items: [], total: 0, page: 1, page_size: 5, total_pages: 0 })) },
  walletsApi: { list: jest.fn(() => Promise.resolve({ items: [], total: 0, page: 1, page_size: 1, total_pages: 0 })) },
  investigationsApi: { list: jest.fn(() => Promise.resolve({ items: [], total: 0, page: 1, page_size: 5, total_pages: 0 })) },
  healthApi: {
    check: jest.fn(() =>
      Promise.resolve({
        status: "healthy",
        version: "1.0.0",
        timestamp: new Date().toISOString(),
        services: { database: "connected", neo4j: "connected", redis: "connected" },
      })
    ),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("DashboardPage", () => {
  it("renders without crashing and shows the page heading", () => {
    renderWithClient(<DashboardPage />);
    expect(screen.getByRole("heading", { name: "FORENSIC ANALYST WORKSPACE" })).toBeInTheDocument();
  });

  it("renders the stat cards", () => {
    renderWithClient(<DashboardPage />);
    expect(screen.getByText("Active Cases")).toBeInTheDocument();
    expect(screen.getByText("Wallets Tracked")).toBeInTheDocument();
    expect(screen.getByText("Investigations Running")).toBeInTheDocument();
    expect(screen.getByText("Completed Traces")).toBeInTheDocument();
  });

  it("shows the platform health section", () => {
    renderWithClient(<DashboardPage />);
    expect(screen.getByText("SYSTEM TELEMETRY & INFRASTRUCTURE HEALTH")).toBeInTheDocument();
  });
});
