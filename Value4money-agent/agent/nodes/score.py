# Place the bid totals against the cleaned pool. No model, no judgement, no prompt.
#
# What this node does, in all it does:
#  1. It takes the totals as each bidder stated them. parse_bid_pdf already compared every line total
#     and the stated total against the sum of its own line items, so a stated total that disagrees
#     with the line items is a fact about the document, not something this node corrects. The report
#     states that disagreement separately, and the figure benchmarked here is the one the bidder
#     actually priced. Swapping in the computed total would describe a number nobody quoted.
#  2. It hands those totals and the pool quality_check built to benchmark_price under the run's own
#     run_id, so the statistics land in audit_log with the bids and the pool they came from.
#  3. It stores the tool's result untouched. That is where the median, the quartiles, the confidence
#     and each bid's position come from, and no arithmetic happens anywhere in this file.
#
# A pool of zero is not an error here. benchmark_price reports confidence insufficient with no
# statistics and no labels, and the draft turns that into a report saying there was not enough
# evidence, which is the honest outcome when the research loop could not find comparables.
#
# What it returns: the benchmark, and nothing else.

from typing import Any, Dict, List

from agent.state import AgentState
from agent.tools import benchmark_price


def score_node(state: AgentState) -> dict:
    """Benchmark the stated bid totals against the cleaned pool."""
    bids: List[Dict[str, Any]] = [{"bidder": bid["bidder"], "total": bid["stated_total"]}
                                  for bid in state["bids"]]
    return {"benchmark": benchmark_price(state["run_id"], bids, state.get("pool", []))}
