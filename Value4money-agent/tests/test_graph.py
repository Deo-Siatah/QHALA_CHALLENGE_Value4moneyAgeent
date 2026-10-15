import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END

from agent import graph
from agent.graph import (build_graph, route_after_intake, route_after_quality_check,
                         route_after_verify_sources, route_after_approval)
from agent.state import initial_state
from config import settings

NODES = ["intake", "research", "quality_check", "score", "draft", "verify_sources", "approval", "file"]


def compiled_edges():
    """The compiled graph's edges, as (source, target) pairs."""
    drawn = build_graph().get_graph()
    return {(edge.source, edge.target) for edge in drawn.edges}


def test_every_node_is_registered():
    assert set(build_graph().get_graph().nodes) - {"__start__", "__end__"} == set(NODES)


def test_start_goes_to_intake_and_file_ends_the_run():
    edges = compiled_edges()

    assert ("__start__", "intake") in edges
    assert ("file", "__end__") in edges


def test_intake_routes_to_research_when_bids_were_parsed():
    assert route_after_intake({"bids": [{"bidder": "Apex"}]}) == "research"


def test_intake_ends_the_run_when_no_bid_parsed():
    assert route_after_intake({"bids": []}) == END
    assert route_after_intake({"parse_issues": ["file unreadable"]}) == END


@pytest.mark.parametrize("attempts, expected", [(1, "research"), (2, "research"), (3, "score")])
def test_quality_searches_again_while_the_pool_is_too_thin(attempts, expected):
    assert route_after_quality_check({"pool_size": 4, "search_attempts": attempts}) == expected


def test_quality_does_not_search_again_when_the_pool_is_usable():
    assert route_after_quality_check({"pool_size": 6, "search_attempts": 1}) == "score"


def test_quality_scores_as_soon_as_the_pool_is_good_enough():
    assert route_after_quality_check({"pool_size": settings.good_pool_n, "search_attempts": 1}) == "score"


def test_quality_measures_the_pool_after_the_model_judged_it():
    state = {"pool_size": 3, "search_attempts": 1,
             "quality": {"pool_size": 20, "enough_comparables": True}}

    assert route_after_quality_check(state) == "research"


def test_quality_treats_an_unmeasured_pool_as_the_thinnest_one():
    assert route_after_quality_check({}) == "research"
    assert route_after_quality_check({"pool_size": 0, "search_attempts": 1}) == "research"
    assert route_after_quality_check({"pool_size": 0, "search_attempts": settings.max_research_attempts}) == "score"


@pytest.mark.parametrize("rounds, expected", [(1, "draft"), (2, "approval")])
def test_verify_loops_back_to_draft_until_the_cap(rounds, expected):
    state = {"verify_ok": False, "verify_rounds": rounds}

    assert route_after_verify_sources(state) == expected


def test_verify_goes_to_approval_once_the_draft_checks_out():
    state = {"verify_ok": True, "verify_rounds": 1}

    assert route_after_verify_sources(state) == "approval"


def test_approval_files_only_when_a_human_approved():
    assert route_after_approval({"approval_status": "approved"}) == "file"


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_approval_ends_the_run_when_nobody_approved(status):
    assert route_after_approval({"approval_status": status}) == END
    assert route_after_approval({}) == END


def test_a_run_loops_to_the_caps_and_finishes(monkeypatch):
    seen = {"research": 0, "draft": 0}

    def fake_intake(state):
        return {"bids": [{"bidder": "Apex", "total": 3_000_000.0}], "search_attempts": 0,
                "quality_attempts": 0, "verify_rounds": 0}

    def fake_research(state):
        seen["research"] += 1
        return {"search_attempts": state["search_attempts"] + 1}

    def fake_quality(state):
        return {"pool_size": 0, "quality": {"pool_size": 0, "enough_comparables": False}}

    def fake_score(state):
        return {"benchmark": {"n": 0, "confidence": "insufficient"}}

    def fake_draft(state):
        seen["draft"] += 1
        return {"review_markdown": "# draft", "verify_ok": False, "verify_rounds": state["verify_rounds"] + 1}

    def fake_verify(state):
        return {"verify_ok": False}

    def fake_approval(state):
        return {"approval_status": "approved", "approved_by": "Grace Wanjiku"}

    def fake_file(state):
        return {"submission": {"report_id": 1}}

    monkeypatch.setattr(graph, "intake_node", fake_intake)
    monkeypatch.setattr(graph, "research_node", fake_research)
    monkeypatch.setattr(graph, "quality_check_node", fake_quality)
    monkeypatch.setattr(graph, "score_node", fake_score)
    monkeypatch.setattr(graph, "draft_node", fake_draft)
    monkeypatch.setattr(graph, "verify_sources_node", fake_verify)
    monkeypatch.setattr(graph, "approval_node", fake_approval)
    monkeypatch.setattr(graph, "file_node", fake_file)

    run = build_graph(InMemorySaver()).invoke(
        initial_state("run-1", ["sample_bids/apex.pdf", "sample_bids/bora.pdf"], "2026-03-01T09:00:00Z"),
        config={"configurable": {"thread_id": "run-1"}})

    assert seen == {"research": 3, "draft": 2}
    assert run["search_attempts"] == 3
    assert run["verify_rounds"] == 2
    assert run["submission"] == {"report_id": 1}
    assert run["approved_by"] == "Grace Wanjiku"
