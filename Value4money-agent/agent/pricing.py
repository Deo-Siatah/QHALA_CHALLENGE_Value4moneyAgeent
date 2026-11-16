"""Turn token counts into a USD cost using the prices configured for the model.

The prices are per million tokens, the unit providers publish. A model with no prices configured has
no cost to claim, so this returns None rather than a zero a reader would mistake for "free".
"""

from typing import Optional

from config import settings

TOKENS_PER_MTOK = 1_000_000


def cost_usd(input_tokens: int, output_tokens: int) -> Optional[float]:
    """The USD cost of one model call, or None when either price is not configured."""
    input_price = settings.llm_input_usd_per_mtok
    output_price = settings.llm_output_usd_per_mtok
    if input_price is None or output_price is None:
        return None
    return ((input_tokens / TOKENS_PER_MTOK) * input_price
            + (output_tokens / TOKENS_PER_MTOK) * output_price)
