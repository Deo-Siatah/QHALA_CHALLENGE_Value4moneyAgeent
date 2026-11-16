# The unit economics of one completed review. These are the figures a judge re-computes from the
# tokens and model calls in the run, so the arithmetic lives in one place and is tested directly.

import pytest

from agent import economics
from config import settings


def test_cost_per_answer_is_the_llm_cost_shared_across_the_model_calls(monkeypatch):
    monkeypatch.setattr(settings, "tool_fee_usd_per_outcome", 0.0)

    figures = economics.unit_economics(total_llm_cost_usd=0.0036, model_calls=3)

    assert figures["cost_per_answer_usd"] == pytest.approx(0.0012)
    assert figures["total_llm_cost_usd"] == pytest.approx(0.0036)
    assert figures["model_calls"] == 3
    assert "price_per_outcome_usd" not in figures
    assert "margin_per_outcome_usd" not in figures


def test_cost_per_outcome_adds_the_tool_fee_to_the_llm_cost(monkeypatch):
    monkeypatch.setattr(settings, "tool_fee_usd_per_outcome", 0.10)

    figures = economics.unit_economics(total_llm_cost_usd=0.0036, model_calls=3)

    assert figures["cost_per_outcome_usd"] == pytest.approx(0.1036)
    assert figures["tool_fee_usd"] == pytest.approx(0.10)


def test_a_run_with_no_model_calls_has_no_cost_per_answer_or_outcome(monkeypatch):
    monkeypatch.setattr(settings, "tool_fee_usd_per_outcome", 0.10)

    figures = economics.unit_economics(total_llm_cost_usd=None, model_calls=0)

    assert figures["cost_per_answer_usd"] is None
    assert figures["cost_per_outcome_usd"] is None
    assert "price_per_outcome_usd" not in figures
    assert "margin_per_outcome_usd" not in figures
