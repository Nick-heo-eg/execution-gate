from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, cast

from .core import Gate
from .decision import ActionEnvelope
from .logger import emit_audit

F = TypeVar("F", bound=Callable[..., Any])


class BlockedByGate(RuntimeError):
    def __init__(self, message: str, *, decision_reason: Optional[str] = None, reason_code: Optional[str] = None) -> None:
        super().__init__(message)
        self.decision_reason = decision_reason
        self.reason_code = reason_code


def enforce(
    gate: Gate,
    *,
    intent_builder: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Callable[[F], F]:
    """
    Decorator enforcing Execution Boundary Core Spec v0.1 flow:

      ActionEnvelope → Evaluator → Decision → Ledger append → Runtime (ALLOW only)

    Ledger append is unconditional — DENY decisions are recorded before blocking.
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 1. Build intent
            intent = intent_builder(*args, **kwargs) if intent_builder else {
                "actor": "agent",
                "action": func.__name__,
                "metadata": {},
            }

            # 2. Build ActionEnvelope
            action = intent.get("action", func.__name__)
            metadata = intent.get("metadata") or {}
            envelope = ActionEnvelope.build(
                action_type=str(action),
                resource=intent.get("resource", "__unspecified__"),
                parameters=metadata if isinstance(metadata, dict) else {},
            )

            # 3. Evaluate (side-effect free)
            decision = gate.evaluate(envelope)

            # 4. Ledger append (unconditional — DENY also recorded)
            emit_audit(
                envelope=envelope,
                decision=decision,
                platform=gate.platform,
                model=gate.model,
                out_file=gate.audit_file,
            )

            # 5. Runtime: ALLOW only
            if not decision.allowed:
                raise BlockedByGate(
                    f"Blocked by gate: {decision.reason_code}",
                    decision_reason=decision.reason,
                    reason_code=decision.reason_code,
                )

            return func(*args, **kwargs)

        return cast(F, wrapper)
    return decorator
