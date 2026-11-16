import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ModelCall, UnitEconomics as UnitEconomicsFigures } from "../api/types";
import { UnitEconomics } from "../components/UnitEconomics";

const figures: UnitEconomicsFigures = {
  model_calls: 3,
  cost_per_answer_usd: 0.0012,
  total_llm_cost_usd: 0.0036,
  tool_fee_usd: 0,
  cost_per_outcome_usd: 0.0036,
};

const calls: ModelCall[] = [
  { step: "bid_intake", prompt: "judge_similar_awards", input_tokens: 1292,
    output_tokens: 306, cost_usd: 0.0004 },
  { step: "quality_check", prompt: "judge_next_search_move", input_tokens: 3217,
    output_tokens: 2226, cost_usd: 0.0018 },
  { step: "draft", prompt: "draft_review_wording", input_tokens: 1047,
    output_tokens: 465, cost_usd: 0.0014 },
];

describe("compute used", () => {
  it("is a highlighted section, not a card, and names the figures a judge checks", () => {
    render(<UnitEconomics economics={figures} calls={calls} />);

    const section = screen.getByRole("region", { name: "Compute used" });
    expect(section).toHaveClass("border-accent/30");
    expect(screen.getByText("Compute used")).toBeInTheDocument();
    expect(screen.queryByText("Unit economics")).not.toBeInTheDocument();
    expect(screen.getByText("Cost per answer")).toBeInTheDocument();
    expect(screen.getByText("$0.0012")).toBeInTheDocument();
    expect(screen.getByText("Model calls per outcome")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Cost per outcome")).toBeInTheDocument();
    expect(screen.getAllByText("$0.0036").length).toBeGreaterThanOrEqual(2);
  });

  it("does not show the removed value ladder, price or margin", () => {
    render(<UnitEconomics economics={figures} calls={calls} />);

    expect(screen.queryByText(/willingness to pay/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/user's cost today/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/SMS/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/hosting/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/price per outcome/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/margin per outcome/i)).not.toBeInTheDocument();
  });

  it("shows the model calls behind a disclosure, without a prompt column", () => {
    render(<UnitEconomics economics={figures} calls={calls} />);

    expect(screen.getByText("Model calls (3)")).toBeInTheDocument();
    expect(screen.queryByText("Prompt")).not.toBeInTheDocument();
    expect(screen.queryByText("judge_similar_awards")).not.toBeInTheDocument();
    expect(screen.getByText("1.3k in / 306 out")).toBeInTheDocument();
  });
});
