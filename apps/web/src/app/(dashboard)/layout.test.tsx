import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DashboardLayout from "./layout";

// NOTE (WS7): as of this test's authoring, `(dashboard)/layout.tsx` exports
// `DashboardLayout` as a NAMED export only — there is no `export default`.
// WS5 owns fixing that (see plan section "WS5 — Frontend Auth & Shell":
// "Fix `(dashboard)/layout.tsx`: it currently has no `export` at all — add
// `export default function DashboardLayout(...)`"). Once WS5 lands, add:
//
//   import DashboardLayout from "./layout";
//   expect(DashboardLayout).toBeDefined();
//
// to lock in the regression fix. For now this test only covers the named
// export that exists today.

jest.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() }),
}));

describe("DashboardLayout (named export)", () => {
  it("renders the sidebar navigation and children", () => {
    render(
      <DashboardLayout>
        <div>page content</div>
      </DashboardLayout>
    );

    expect(screen.getByText("TRACE-X")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Cases")).toBeInTheDocument();
    expect(screen.getByText("page content")).toBeInTheDocument();
  });

  it("toggles collapsed state when the collapse button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <DashboardLayout>
        <div>content</div>
      </DashboardLayout>
    );

    const toggle = screen.getByLabelText("Collapse sidebar");
    await user.click(toggle);

    expect(screen.getByLabelText("Expand sidebar")).toBeInTheDocument();
  });
});
