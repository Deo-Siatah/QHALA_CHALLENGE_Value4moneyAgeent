import type { ModelCall, UnitEconomics as UnitEconomicsFigures } from "../api/types";
import { tokenCount, USD } from "../lib/format";

/** The compute cost of one completed review, measured from the run's own logs. */
export function UnitEconomics({
  economics,
  calls,
}: {
  economics: UnitEconomicsFigures;
  calls: ModelCall[];
}) {
  return (
    <section
      aria-label="Compute used"
      className="rounded-xl border border-accent/30 bg-accent-soft/25 px-5 py-5 shadow-soft"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-[0.7rem] font-semibold tracking-[0.16em] text-accent uppercase">
            Compute used
          </p>
          <h2 className="mt-1 text-base font-semibold text-ink-900">One completed tender review</h2>
        </div>
        <p className="text-xs text-ink-500">Measured from this run's model calls</p>
      </div>

      <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Figure label="Cost per answer" value={USD(economics.cost_per_answer_usd)} />
        <Figure label="Model calls per outcome" value={String(economics.model_calls)} />
        <Figure label="Total LLM cost" value={USD(economics.total_llm_cost_usd)} />
        <Figure label="Tool fee" value={USD(economics.tool_fee_usd)} />
        <Figure label="Cost per outcome" value={USD(economics.cost_per_outcome_usd)} />
      </dl>

      <p className="mt-4 text-xs text-ink-500">
        {USD(economics.cost_per_answer_usd)} per answer × {economics.model_calls} model calls +{" "}
        {USD(economics.tool_fee_usd)} tool fee = {USD(economics.cost_per_outcome_usd)} cost per outcome.
      </p>

      <details className="mt-4 rounded-md border border-ink-200 bg-paper/70">
        <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-ink-700">
          Model calls ({calls.length})
        </summary>
        <div className="overflow-x-auto border-t border-ink-200">
          <table className="w-full text-left text-xs">
            <thead className="text-ink-500">
              <tr>
                <th className="px-3 py-2 font-medium">Step</th>
                <th className="px-3 py-2 font-medium">Tokens</th>
                <th className="px-3 py-2 font-medium">Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-200">
              {calls.map((call, index) => (
                <tr key={`${call.step}-${index}`}>
                  <td className="px-3 py-2 text-ink-700">{call.step}</td>
                  <td className="px-3 py-2 tabular-nums text-ink-600">
                    {tokenCount(call.input_tokens, call.output_tokens)}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-ink-600">{USD(call.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-500">{label}</dt>
      <dd className="mt-1 text-lg font-semibold tabular-nums text-ink-900">{value}</dd>
    </div>
  );
}
