"""
Execution Boundary Observability — OTel integration (optional).

Install: pip install execution-gate[otel]

If opentelemetry-api is not installed, all functions in this module
return no-ops. Gate behavior is identical with or without OTel.

Environment variables (standard OTel SDK):
  OTEL_EXPORTER_OTLP_ENDPOINT  — e.g. http://localhost:4317
  OTEL_SERVICE_NAME            — defaults to "execution-gate"

eb.* semantic conventions: execution-observability-profile/semantic/attributes.md
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Optional

try:
    from opentelemetry import trace
    from opentelemetry.trace import Span, StatusCode
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


def _tracer() -> Any:
    if not _OTEL_AVAILABLE:
        return None
    return trace.get_tracer("execution-gate", schema_url="https://opentelemetry.io/schemas/1.24.0")


@contextmanager
def eb_evaluate_span(
    *,
    envelope_id: str,
    action_type: str,
) -> Generator[Optional[Any], None, None]:
    """
    Context manager wrapping eb.evaluate span.

    Usage (inside Gate.evaluate):
        with eb_evaluate_span(envelope_id=..., action_type=...) as span:
            # ... evaluation logic ...
            set_decision_attributes(span, decision)
    """
    tracer = _tracer()
    if tracer is None:
        yield None
        return

    with tracer.start_as_current_span("eb.evaluate") as span:
        span.set_attribute("eb.envelope_id", envelope_id)
        span.set_attribute("eb.action_type", action_type)
        yield span


def set_decision_attributes(span: Optional[Any], decision: Any) -> None:
    """
    Set eb.* decision attributes on an active span.
    No-op if span is None (OTel not installed).
    """
    if span is None or not _OTEL_AVAILABLE:
        return

    span.set_attribute("eb.decision", decision.result)
    span.set_attribute("eb.reason_code", decision.reason_code)
    span.set_attribute("eb.ledger_commit", True)  # set True here; enforcement sets False on commit failure

    if decision.proof_hash:
        # First 8 chars only — avoid high-cardinality attribute on metrics
        span.set_attribute("eb.proof_hash", decision.proof_hash[:8])

    if decision.result == "DENY":
        # Mark span as error for keep-errors tail sampling policy to catch failures
        # DENY is not an error in the gate sense — it is the correct outcome.
        # We do NOT set ERROR status here; keep-deny handles retention independently.
        pass

    if decision.result in ("DENY", "HOLD"):
        # Ensure these spans survive tail sampling via keep-deny / keep-hold policies.
        # The span status remains OK — DENY is a valid, expected outcome.
        span.set_attribute("eb.decision_final", True)


def record_ledger_commit_failure(span: Optional[Any]) -> None:
    """
    Call if ledger append fails after decision.
    Sets eb.ledger_commit=False and marks span as error.
    """
    if span is None or not _OTEL_AVAILABLE:
        return
    span.set_attribute("eb.ledger_commit", False)
    span.set_status(StatusCode.ERROR, "ledger commit failed")


@contextmanager
def eb_ledger_append_span() -> Generator[Optional[Any], None, None]:
    """Context manager for eb.ledger.append span."""
    tracer = _tracer()
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span("eb.ledger.append") as span:
        yield span
