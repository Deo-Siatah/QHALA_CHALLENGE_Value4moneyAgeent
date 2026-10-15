# Send the run to Opik so its shape can be read: which node, which tool, which prompt, how long.
#
# Tracing is for seeing what the agent did and how slowly. It is never the record of what happened:
# that is audit_log, in Postgres, and it is written whether or not Opik is reachable. A run that
# traces nothing is a run that still filed its evidence.
#
# When Opik is switched off, or no API key is set, every function here becomes the identity and the
# run behaves exactly as it does without tracing. 
# One trace per invocation, with everything nested inside it. The trace is threaded by run_id, so a
# run that pauses for approval and the later command that resumes it read as one conversation.
#
# Where the spans come from:
#   the run    agent/run.py        one trace for a start or a resume
#   a node     agent/graph.py      what each of the eight steps was doing
#   a tool     agent/tools.py every call made to one of the six tools
#   a model    agent/llm.py        every prompt sent to Hasibu

from typing import Any, Callable, Optional

from config import settings

try:
    import opik
except ImportError:          # Opik is optional: the agent runs without it
    opik = None              # type: ignore[assignment]

_enabled = False


def enabled() -> bool:
    """Whether traces are going anywhere at all."""
    return _enabled


def init_tracing(run_id: Optional[str] = None) -> bool:
    """Point Opik at the configured project. False means tracing is off and nothing changes."""
    global _enabled
    _enabled = False
    if opik is None or not settings.opik_enabled or not settings.opik_api_key:
        return False

    opik.configure(api_key=settings.opik_api_key,
                   workspace=settings.opik_workspace or None,
                   project_name=settings.opik_project,
                   use_local=False)
    _enabled = True
    trace_run(run_id)
    return True


def traced(span_type: str = "general", name: Optional[str] = None) -> Callable:
    """Decorate a function so each call is one Opik span of the given kind."""
    def decorate(fn: Callable) -> Callable:
        if not _enabled:
            return fn
        return opik.track(name if name is not None else fn.__name__, type=span_type)(fn)

    return decorate


def annotate_llm(prompt_name: str, model: str, provider: str,
                 usage: Optional[dict] = None, **metadata: Any) -> None:
    """Describe the model call in the current span, so Opik can compute its cost."""
    if not _enabled:
        return
    _quietly(lambda: opik.opik_context.update_current_span(
        model=model, provider=provider, usage=usage or {},
        metadata={"prompt": prompt_name, **metadata}))


def trace_run(run_id: Optional[str], **metadata: Any) -> None:
    """Thread the trace by run_id, so a pause and its later approval read as one conversation."""
    if not _enabled or not run_id:
        return
    _quietly(lambda: opik.opik_context.update_current_trace(thread_id=run_id, metadata=metadata))


def _quietly(action: Callable[[], Any]) -> None:
    """Do the Opik side of things without ever letting them break a run.

    Annotating a span only works inside one. Called outside, Opik raises, and a trace is not worth
    failing a tender review over.
    """
    try:
        action()
    except Exception:
        pass


def flush() -> None:
    """Send everything queued before the process ends. The SDK batches, so this matters."""
    if _enabled:
        opik.flush_tracker()
