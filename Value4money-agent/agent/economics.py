"""The compute cost of one completed tender review.

One outcome is one full run. The model cost is measured by the callbacks; the tool fee is configured
because it is a commercial choice, not a fact the agent can observe.
"""

from typing import Any, Dict, Optional

from config import settings


def unit_economics(total_llm_cost_usd: Optional[float], model_calls: int) -> Dict[str, Any]:
    """Cost per answer and cost per outcome, using only the figures that are configured."""
    tool_fee = settings.tool_fee_usd_per_outcome
    if model_calls <= 0 or total_llm_cost_usd is None:
        cost_per_answer = None
        cost_per_outcome = None
    else:
        cost_per_answer = total_llm_cost_usd / model_calls
        cost_per_outcome = total_llm_cost_usd + tool_fee
    return {
        "model_calls": model_calls,
        "cost_per_answer_usd": cost_per_answer,
        "total_llm_cost_usd": total_llm_cost_usd,
        "tool_fee_usd": tool_fee,
        "cost_per_outcome_usd": cost_per_outcome,
    }
