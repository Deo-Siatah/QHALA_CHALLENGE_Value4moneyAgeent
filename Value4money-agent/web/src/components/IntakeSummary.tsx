import type { TenderResult } from "../api/types";
import { KES } from "../lib/format";
import { Badge } from "./ui/badge";

const FIELD_WORDS: Record<string, string> = {
  reference: "Tender reference",
  title: "Title",
  buyer: "Buyer",
  county: "County",
  method: "Method",
  closing_date: "Closing date",
  budget_kes: "Budget",
};

function fieldWord(name: string): string {
  return FIELD_WORDS[name] ?? name.replaceAll("_", " ");
}

function fieldValue(name: string, value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "not stated";
  }
  if (name === "budget_kes" && typeof value === "number") {
    return KES(value);
  }
  return String(value);
}

/**
 * What the tender document said, with the page it came from.
 *
 * A value without a source is not shown as fact: the extractor only keeps labelled lines, and this
 * table repeats its source beside every value. Missing fields are named rather than filled in.
 */
export function IntakeSummary({
  tender,
  tenderMissing = [],
  issues = [],
}: {
  tender?: TenderResult;
  tenderMissing?: string[];
  issues?: string[];
}) {
  const fields = Object.entries(tender?.fields ?? {});
  const missing = tender?.missing ?? tenderMissing;

  return (
    <div className="space-y-4">
      {fields.length > 0 ? (
        <div className="overflow-x-auto rounded-md border border-ink-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-ink-100 text-xs tracking-wide text-ink-500 uppercase">
              <tr>
                <th className="px-3 py-2 font-semibold">Field</th>
                <th className="px-3 py-2 font-semibold">Value</th>
                <th className="px-3 py-2 font-semibold">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-200">
              {fields.map(([name, field]) => (
                <tr key={name}>
                  <td className="px-3 py-2 font-medium text-ink-900">{fieldWord(name)}</td>
                  <td className="px-3 py-2 text-ink-700">{fieldValue(name, field.value)}</td>
                  <td className="px-3 py-2 text-xs text-ink-500">
                    {field.source?.page ? `page ${field.source.page}` : "no page"}
                    {field.source?.text ? ` · ${field.source.text}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-ink-500">No tender fields were read.</p>
      )}

      {missing.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-ink-500">
          <span>Missing from the tender:</span>
          {missing.map((name) => (
            <Badge key={name} tone="ask">{fieldWord(name)}</Badge>
          ))}
        </div>
      )}

      {issues.length > 0 && (
        <ul className="list-disc space-y-1 pl-4 text-xs text-ask">
          {issues.map((issue) => <li key={issue}>{issue}</li>)}
        </ul>
      )}
    </div>
  );
}
