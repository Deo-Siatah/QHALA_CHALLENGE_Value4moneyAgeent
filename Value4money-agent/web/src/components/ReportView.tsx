import { useQuery } from "@tanstack/react-query";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import { Copy, FileCode2, FileDown, Printer } from "lucide-react";
import { useState } from "react";
import { getReportMarkdown, reportUrl } from "../api/client";
import type { RunSnapshot } from "../api/types";
import { Button, buttonVariants } from "./ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "./ui/card";
import { Table } from "./ui/input";
import { cn } from "../lib/utils";

/**
 * The evidence file, rendered as the agent wrote it.
 *
 * The markdown is sanitised because it is model output rendered as HTML. The downloads are the
 * server's own renderings of the same review dict, and the print stylesheet makes the browser's Save
 * as PDF a third option that costs nothing.
 */
export function ReportView({ runId, snapshot }: { runId: string; snapshot: RunSnapshot }) {
  const report = useQuery({
    queryKey: ["report", runId, snapshot.status],
    queryFn: () => getReportMarkdown(runId),
    enabled: snapshot.status !== "queued" && snapshot.status !== "running",
    retry: false,
  });
  const [copied, setCopied] = useState(false);
  const [orientation, setOrientation] = useState<"portrait" | "landscape">("landscape");
  const [paperSize, setPaperSize] = useState<"A4" | "Letter">("A4");
  const printOptions = { orientation, paperSize };

  return (
    <Card className="print-only">
      <CardHeader className="flex flex-wrap items-center justify-between gap-3">
        <CardTitle>The evidence file</CardTitle>
        <div className="no-print flex flex-wrap gap-2">
          <label className="flex items-center gap-2 text-xs text-ink-500">
            <span>Page</span>
            <select aria-label="Page orientation" value={orientation}
              onChange={(event) => setOrientation(event.target.value as typeof orientation)}
              className="rounded border border-ink-300 bg-paper px-2 py-1 text-xs text-ink-700">
              <option value="landscape">Landscape</option>
              <option value="portrait">Portrait</option>
            </select>
          </label>
          <label className="flex items-center gap-2 text-xs text-ink-500">
            <span>Size</span>
            <select aria-label="Paper size" value={paperSize}
              onChange={(event) => setPaperSize(event.target.value as typeof paperSize)}
              className="rounded border border-ink-300 bg-paper px-2 py-1 text-xs text-ink-700">
              <option value="A4">A4</option>
              <option value="Letter">Letter</option>
            </select>
          </label>
          <a
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            href={reportUrl(runId, "pdf", printOptions)}
            target="_blank"
            rel="noreferrer"
          >
            <Printer className="size-4" />
            Print report
          </a>
          <Button
            variant="outline"
            size="sm"
            disabled={!report.data}
            onClick={async () => {
              if (report.data) {
                await navigator.clipboard.writeText(report.data);
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1500);
              }
            }}
          >
            <Copy className="size-4" />
            {copied ? "Copied" : "Copy markdown"}
          </Button>
          <a className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            href={reportUrl(runId, "pdf", printOptions)}>
            <FileDown className="size-4" />
            Download PDF
          </a>
          <a className={cn(buttonVariants({ variant: "outline", size: "sm" }))} href={reportUrl(runId, "tex")}>
            <FileCode2 className="size-4" />
            Download LaTeX
          </a>
        </div>
      </CardHeader>
      <CardBody>
        {report.isPending && <p className="text-sm text-ink-500">Waiting for the report…</p>}
        {report.isError && (
          <p className="text-sm text-ink-500">
            There is no report to show yet. It appears once the file has been written.
          </p>
        )}
        {report.data && (
          <article className="max-w-none text-sm leading-relaxed text-ink-700">
            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
              {report.data}
            </Markdown>
          </article>
        )}
      </CardBody>
    </Card>
  );
}

/** Findings with the records each rests on. No source, no finding, so the ids are shown beside
 * every one of them rather than collected at the end. */
export function Findings({ snapshot }: { snapshot: RunSnapshot }) {
  if (snapshot.findings.length === 0) {
    return (
      <p className="rounded-md bg-ink-100 px-4 py-3 text-sm text-thin">
        No findings were recorded for this review.
      </p>
    );
  }
  return (
    <Table>
      <tbody className="divide-y divide-ink-200">
        {snapshot.findings.map((finding, index) => (
          <tr key={`${index}-${finding.text.slice(0, 12)}`}>
            <td className="w-8 align-top py-2 text-xs tabular-nums text-ink-400">{index + 1}</td>
            <td className="py-2 align-top text-sm text-ink-700">
              {finding.text}
              <span className="mt-1 block text-xs text-ink-400">
                Sources: {finding.sources.join(", ")}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
