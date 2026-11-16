import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { IntakeSummary } from "../components/IntakeSummary";

describe("what the tender said", () => {
  it("shows each field with the page it came from", () => {
    render(
      <IntakeSummary
        tender={{
          fields: {
            reference: { value: "TENDER/NC/2026/014",
              source: { page: 1, text: "Tender No.: TENDER/NC/2026/014" } },
            title: { value: "Construction of classroom blocks",
              source: { page: 2, text: "Title: Construction of classroom blocks" } },
            budget_kes: { value: 5_000_000, source: { page: 2, text: "Budget: 5,000,000" } },
          },
        }}
      />,
    );

    expect(screen.getByText("Tender reference")).toBeInTheDocument();
    expect(screen.getByText("TENDER/NC/2026/014")).toBeInTheDocument();
    expect(screen.getByText("Construction of classroom blocks")).toBeInTheDocument();
    expect(screen.getByText("KES 5,000,000.00")).toBeInTheDocument();
    expect(screen.getByText(/page 1/)).toBeInTheDocument();
    expect(screen.getByText(/Tender No\./)).toBeInTheDocument();
  });

  it("names a missing field rather than filling it in", () => {
    render(<IntakeSummary tender={{ fields: {}, missing: ["reference", "title"] }} />);

    expect(screen.getByText("Missing from the tender:")).toBeInTheDocument();
    expect(screen.getAllByText(/reference|Title/).length).toBeGreaterThan(0);
  });

  it("lists the intake issues in plain words", () => {
    render(
      <IntakeSummary tender={{ fields: {} }}
        issues={["Apex: needs_review (low confidence)"]} />,
    );

    expect(screen.getByText("Apex: needs_review (low confidence)")).toBeInTheDocument();
  });

  it("says plainly when no tender was supplied", () => {
    render(<IntakeSummary />);

    expect(screen.getByText("No tender fields were read.")).toBeInTheDocument();
  });
});
