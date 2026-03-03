"""
OTel instrumentation for execution-gate.

This module is imported only if opentelemetry-api is installed.
It is never imported directly by gate/core.py.
core.py loads it through _load_instrumentation() which swallows all failures.

eb.* semantic conventions: execution-observability-profile/semantic/attributes.md
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Optional

from opentelemetry import trace
from opentelemetry.trace import StatusCode

_tracer = trace.get_tracer(
    "execution-gate",
    schema_url="https://opentelemetry.io/schemas/1.24.0",
)


@contextmanager
def eb_evaluate_span(
    *,
    envelope_id: str,
    action_type: str,
) -> Generator[Any, None, None]:
    with _tracer.start_as_current_span("eb.evaluate") as span:
        span.set_attribute("eb.envelope_id", envelope_id)
        span.set_attribute("eb.action_type", action_type)
        yield span


def set_decision_attributes(span: Any, decision: Any) -> None:
    span.set_attribute("eb.decision", decision.result)
    span.set_attribute("eb.reason_code", decision.reason_code)
    span.set_attribute("eb.ledger_commit", True)
    if decision.proof_hash:
        span.set_attribute("eb.proof_hash", decision.proof_hash[:8])


def record_ledger_commit_failure(span: Any) -> None:
    span.set_attribute("eb.ledger_commit", False)
    span.set_status(StatusCode.ERROR, "ledger commit failed")


@contextmanager
def eb_ledger_append_span() -> Generator[Any, None, None]:
    with _tracer.start_as_current_span("eb.ledger.append") as span:
        yield span
