import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { RunSnapshot } from "../api/types";

vi.mock("../api/client", () => ({
  getReportMarkdown: vi.fn(() => Promise.resolve("# populated report")),
  reportUrl: (runId: string, format: string, options?: {
    orientation?: "portrait" | "landscape";
    paperSize?: "A4" | "Letter";
  }) => {
    const query = new URLSearchParams();
    if (options?.orientation) query.set("orientation", options.orientation);
    if (options?.paperSize) query.set("paper_size", options.paperSize);
    return `/api/runs/${runId}/report.${format}?${query.toString()}`;
  },
}));

const { ReportView } = await import("../components/ReportView");

describe("printable report", () => {
  it("keeps the report body visible when the page is printed", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ReportView runId="run-1" snapshot={{ status: "filed" } as RunSnapshot} />
      </QueryClientProvider>,
    );

    const title = await screen.findByText("The evidence file");
    expect(title.closest(".print-only")).not.toBeNull();
  });

  it("updates print and PDF links before the report is opened", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ReportView runId="run-1" snapshot={{ status: "filed" } as RunSnapshot} />
      </QueryClientProvider>,
    );

    await screen.findByText("The evidence file");
    const orientation = screen.getByRole("combobox", { name: "Page orientation" });
    const paperSize = screen.getByRole("combobox", { name: "Paper size" });
    const printLink = screen.getByRole("link", { name: /print report/i });
    const pdfLink = screen.getByRole("link", { name: /download pdf/i });

    expect(printLink).toHaveAttribute("href", "/api/runs/run-1/report.pdf?orientation=landscape&paper_size=A4");
    expect(pdfLink).toHaveAttribute("href", "/api/runs/run-1/report.pdf?orientation=landscape&paper_size=A4");

    const { fireEvent } = await import("@testing-library/react");
    fireEvent.change(orientation, { target: { value: "portrait" } });
    fireEvent.change(paperSize, { target: { value: "Letter" } });

    expect(printLink).toHaveAttribute("href", "/api/runs/run-1/report.pdf?orientation=portrait&paper_size=Letter");
    expect(pdfLink).toHaveAttribute("href", "/api/runs/run-1/report.pdf?orientation=portrait&paper_size=Letter");
  });
});