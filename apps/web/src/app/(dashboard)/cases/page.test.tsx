import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CasesPage from "./page";

jest.mock("@/lib/api", () => ({
  casesApi: {
    list: jest.fn(() => Promise.resolve({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 })),
    create: jest.fn(() => Promise.resolve({})),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("CasesPage", () => {
  it("renders without crashing and shows the page heading", () => {
    renderWithClient(<CasesPage />);
    expect(screen.getByRole("heading", { name: "Cases" })).toBeInTheDocument();
  });

  it("shows the New Case action", () => {
    renderWithClient(<CasesPage />);
    expect(screen.getByRole("button", { name: /New Case/i })).toBeInTheDocument();
  });

  it("shows a search input for filtering cases", () => {
    renderWithClient(<CasesPage />);
    expect(screen.getByPlaceholderText("Search cases...")).toBeInTheDocument();
  });
});
