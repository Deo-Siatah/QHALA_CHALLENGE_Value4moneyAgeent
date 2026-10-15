import sys
import types

import pytest

from agent import tracing
from agent.tracing import annotate_llm, flush, init_tracing, traced, trace_run


def fake_opik():
    """A stand-in for the opik module, recording what tracing asked it to do."""
    calls = []

    module = types.ModuleType("opik")

    def configure(**kwargs):
        calls.append(("configure", kwargs))

    def track(name=None, **kwargs):
        def decorate(fn):
            calls.append(("track", getattr(name, "__name__", name), kwargs.get("type")))
            return fn

        return decorate

    def flush_tracker():
        calls.append(("flush",))

    context = types.SimpleNamespace(
        update_current_span=lambda **kwargs: calls.append(("span", kwargs)),
        update_current_trace=lambda **kwargs: calls.append(("trace", kwargs)),
    )

    module.configure = configure
    module.track = track
    module.flush_tracker = flush_tracker
    module.opik_context = context
    module.Opik = lambda **kwargs: calls.append(("client", kwargs))
    return module, calls


@pytest.fixture(autouse=True)
def tracing_starts_off(monkeypatch):
    """Tracing is a module flag: start every test with it off, and put it back afterwards.

    Without this, a test that switches tracing on would leave it on for every later test in the
    session, and those tests would try to send real spans to Opik.
    """
    monkeypatch.setattr(tracing, "_enabled", False)


@pytest.fixture
def disabled(monkeypatch):
    """Tracing off, with the opik module absent from the process."""
    monkeypatch.setattr(tracing, "opik", None)
    monkeypatch.setattr(tracing.settings, "opik_enabled", False)
    return monkeypatch


def test_tracing_off_leaves_functions_alone(disabled):
    @traced("tool", "benchmark_price")
    def tool(value):
        return value * 2

    assert tool(21) == 42


def test_tracing_off_reports_itself_as_off(disabled):
    assert init_tracing("run-1") is False
    flush()
    trace_run("run-1")


def test_tracing_off_still_annotates_without_raising(disabled):
    annotate_llm("quality_similarity_judgement", model="qwen", provider="groq",
                 usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})


def test_a_key_configures_opik_with_the_project_and_workspace(monkeypatch):
    module, calls = fake_opik()
    monkeypatch.setattr(tracing, "opik", module)
    monkeypatch.setattr(tracing.settings, "opik_enabled", True)
    monkeypatch.setattr(tracing.settings, "opik_api_key", "opik-secret")
    monkeypatch.setattr(tracing.settings, "opik_workspace", "deo-team")
    monkeypatch.setattr(tracing.settings, "opik_project", "value4money-agent")

    assert init_tracing("run-1") is True

    kind, kwargs = calls[0]
    assert kind == "configure"
    assert kwargs["api_key"] == "opik-secret"
    assert kwargs["workspace"] == "deo-team"
    assert kwargs["project_name"] == "value4money-agent"
    assert kwargs["use_local"] is False


def test_enabled_but_keyless_is_off_and_never_configures(monkeypatch):
    module, calls = fake_opik()
    monkeypatch.setattr(tracing, "opik", module)
    monkeypatch.setattr(tracing.settings, "opik_enabled", True)
    monkeypatch.setattr(tracing.settings, "opik_api_key", "")

    assert init_tracing("run-1") is False
    assert calls == []


def test_a_traced_function_is_tracked_and_still_works(monkeypatch):
    module, calls = fake_opik()
    monkeypatch.setattr(tracing, "opik", module)
    monkeypatch.setattr(tracing.settings, "opik_enabled", True)
    monkeypatch.setattr(tracing.settings, "opik_api_key", "opik-secret")
    init_tracing("run-1")

    @traced("tool", "parse_bid_pdf")
    def parse(path):
        return {"bidder": "Apex"}

    assert parse("a.pdf") == {"bidder": "Apex"}
    assert ("track", "parse_bid_pdf", "tool") in calls


def test_a_model_call_is_annotated_with_its_model_and_usage(monkeypatch):
    module, calls = fake_opik()
    monkeypatch.setattr(tracing, "opik", module)
    monkeypatch.setattr(tracing.settings, "opik_enabled", True)
    monkeypatch.setattr(tracing.settings, "opik_api_key", "opik-secret")
    init_tracing("run-1")

    annotate_llm("draft_review_wording", model="qwen/qwen3.8-27b", provider="groq",
                 usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})

    spans = [kwargs for kind, kwargs in calls if kind == "span"]
    assert spans[0]["model"] == "qwen/qwen3.8-27b"
    assert spans[0]["provider"] == "groq"
    assert spans[0]["usage"]["total_tokens"] == 30


def test_the_trace_is_threaded_by_run_id(monkeypatch):
    module, calls = fake_opik()
    monkeypatch.setattr(tracing, "opik", module)
    monkeypatch.setattr(tracing.settings, "opik_enabled", True)
    monkeypatch.setattr(tracing.settings, "opik_api_key", "opik-secret")
    init_tracing("run-9")

    trace_run("run-9")

    traces = [kwargs for kind, kwargs in calls if kind == "trace"]
    assert traces[0]["thread_id"] == "run-9"


def test_flush_reaches_opik_only_when_tracing_is_on(monkeypatch):
    module, calls = fake_opik()
    monkeypatch.setattr(tracing, "opik", module)
    monkeypatch.setattr(tracing.settings, "opik_enabled", True)
    monkeypatch.setattr(tracing.settings, "opik_api_key", "opik-secret")
    init_tracing("run-1")

    flush()

    assert ("flush",) in calls


def test_a_real_opik_is_installed_so_imports_never_fail():
    import opik  # noqa: F401

    assert hasattr(opik, "track")
