import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import { ClipboardCheck, FileSearch, FileText, Play, Scale, Upload, X } from "lucide-react";
import { startRun } from "../api/client";
import { cn } from "../lib/utils";
import { staged, totalBytes, withoutFile } from "../lib/staging";
import { Button } from "../components/ui/button";
import { Card, CardBody } from "../components/ui/card";

/**
 * Choosing the bids is not the same as starting a review.
 *
 * A run writes audit rows and spends a model call the moment it begins, so nothing happens until a
 * person has looked at what they dropped and pressed the button. Everything is staged here first,
 * listed by name, and can be taken back out.
 */
export function StartPage() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [tender, setTender] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onDrop = useCallback((incoming: File[]) => {
    setError(null);
    setFiles((current) => staged(current, incoming));
  }, []);

  const onTenderDrop = useCallback((incoming: File[]) => {
    setError(null);
    setTender(staged([], incoming)[0] ?? null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: true,
    disabled: busy,
  });

  const {
    getRootProps: getTenderRootProps,
    getInputProps: getTenderInputProps,
    isDragActive: isTenderDragActive,
  } = useDropzone({
    onDrop: onTenderDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
    disabled: busy,
  });

  const begin = async () => {
    if (files.length === 0 || !tender) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const run = await startRun(files, tender);
      navigate(`/runs/${run.run_id}`);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : String(problem));
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 sm:py-12">
      <section className="grid gap-8 lg:grid-cols-[minmax(0,1.05fr)_minmax(22rem,0.95fr)] lg:items-end">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold tracking-[0.18em] text-accent uppercase">Public procurement evidence</p>
          <h1 className="mt-3 max-w-xl text-4xl leading-[1.05] font-semibold tracking-tight text-ink-900 sm:text-5xl">
            Evidence for a tender committee.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-ink-700 sm:text-lg">
            Hasibu reads the tender and bid documents, compares prices with comparable public awards,
            and prepares a sourced file for a human committee to review.
          </p>
          <p className="mt-4 flex items-center gap-2 text-sm font-medium text-accent">
            <ClipboardCheck className="size-4 shrink-0" aria-hidden="true" />
            Hasibu prepares evidence. The committee decides.
          </p>
        </div>

        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1">
          {[
            { icon: FileSearch, title: "Read the documents", text: "Tender fields, bid totals, and arithmetic checks." },
            { icon: Scale, title: "Compare public awards", text: "Comparable records with their sources and years." },
            { icon: ClipboardCheck, title: "Prepare the file", text: "Evidence ready for a named human approval." },
          ].map(({ icon: Icon, title, text }, index) => (
            <div key={title} className="flex gap-3 rounded-lg border border-ink-200 bg-paper/80 px-4 py-3 shadow-soft">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent-soft text-accent">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink-900">{index + 1}. {title}</p>
                <p className="mt-0.5 text-xs leading-5 text-ink-500">{text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <Card className="mt-10 border-accent/20 shadow-lift">
        <CardBody className="border-b border-ink-200 bg-accent-soft/35 px-5 py-4 sm:px-6">
          <div className="flex items-start gap-3">
            <Upload className="mt-0.5 size-5 shrink-0 text-accent" aria-hidden="true" />
            <div>
              <h2 className="text-base font-semibold text-ink-900">Start with the tender and its bids</h2>
              <p className="mt-1 text-sm leading-6 text-ink-600">
                Files are staged first. Nothing starts until you review the list and press Start Analysis.
              </p>
            </div>
          </div>
        </CardBody>
        <CardBody>
          <div
            {...getRootProps()}
            className={cn(
              "flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center",
              isDragActive
                ? "border-accent bg-accent-soft"
                : busy
                  ? "cursor-wait border-ink-200 opacity-60"
                  : "cursor-pointer border-ink-300 hover:border-ink-400",
            )}
          >
            <Upload className="size-5 text-ink-400" />
            <p className="text-sm font-medium text-ink-900">
              {isDragActive ? "Drop the bid PDFs here" : "Drop the bid PDFs here, or choose files"}
            </p>
            <p className="text-xs text-ink-500">
              Every PDF must be a bid for the same tender. Two to eight is usual.
            </p>
            <input {...getInputProps()} />
          </div>

          {files.length > 0 && (
            <div className="mt-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-xs font-semibold tracking-wide text-ink-500 uppercase">
                  Ready to analyse · {files.length} {files.length === 1 ? "file" : "files"} ·{" "}
                  {totalBytes(files)}
                </p>
                <button
                  type="button"
                  onClick={() => setFiles([])}
                  className="text-xs text-ink-500 underline underline-offset-4 hover:text-ink-900"
                >
                  Remove all
                </button>
              </div>
              <ul className="mt-2 divide-y divide-ink-200 rounded-md border border-ink-200">
                {files.map((file) => (
                  <li key={file.name} className="flex items-center gap-3 px-3 py-2">
                    <FileText className="size-4 shrink-0 text-ink-400" />
                    <span className="min-w-0 flex-1 truncate text-sm text-ink-700">{file.name}</span>
                    <span className="shrink-0 text-xs tabular-nums text-ink-400">
                      {totalBytes([file])}
                    </span>
                    <button
                      type="button"
                      aria-label={`remove ${file.name}`}
                      onClick={() => setFiles((current) => withoutFile(current, file.name))}
                      className="shrink-0 rounded p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-900"
                    >
                      <X className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-5 border-t border-ink-200 pt-5">
            <p className="text-xs font-semibold tracking-wide text-ink-500 uppercase">
              Tender document (required)
            </p>
            <div
              {...getTenderRootProps()}
              className={cn(
                "mt-2 flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-6 py-6 text-center",
                isTenderDragActive
                  ? "border-accent bg-accent-soft"
                  : busy
                    ? "cursor-wait border-ink-200 opacity-60"
                    : "cursor-pointer border-ink-300 hover:border-ink-400",
              )}
            >
              <Upload className="size-5 text-ink-400" />
              <p className="text-sm font-medium text-ink-900">
                {isTenderDragActive
                  ? "Drop the tender PDF here"
                  : tender
                    ? tender.name
                    : "Add the tender PDF, or choose a file"}
              </p>
              <p className="text-xs text-ink-500">
                The tender supplies the reference, title, buyer, county, method and budget.
              </p>
              <input {...getTenderInputProps()} />
            </div>
            {tender && (
              <div className="mt-2 flex items-center gap-3 rounded-md border border-ink-200 px-3 py-2">
                <FileText className="size-4 shrink-0 text-ink-400" />
                <span className="min-w-0 flex-1 truncate text-sm text-ink-700">{tender.name}</span>
                <button
                  type="button"
                  aria-label={`remove tender ${tender.name}`}
                  onClick={() => setTender(null)}
                  className="shrink-0 rounded p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-900"
                >
                  <X className="size-3.5" />
                </button>
              </div>
            )}
          </div>

          {error && (
            <p
              role="alert"
              className="mt-4 rounded-md border border-stop/30 bg-stop/5 px-3 py-2 text-sm text-stop"
            >
              {error}
            </p>
          )}

          <Button
            variant="accent"
            size="lg"
            className="mt-5 w-full"
            disabled={files.length === 0 || !tender || busy}
            onClick={begin}
          >
            <Play className="size-4" />
            {busy ? "Starting…" : "Start Analysis"}
          </Button>

          <p className="mt-3 text-xs text-ink-400">
            The tender and bids are read through the same audited tools a terminal run uses. Nothing
            is filed until a named person approves it.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
