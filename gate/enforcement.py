from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, cast

from .core import Gate
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
    Decorator:
      - builds intent deterministically
      - checks via gate
      - emits audit
      - blocks by raising BlockedByGate

    intent_builder signature:
      def intent_builder(*args, **kwargs) -> dict
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            intent = intent_builder(*args, **kwargs) if intent_builder else {
                "actor": "agent",
                "action": func.__name__,
                "metadata": {},
            }

            decision = gate.check(intent)
            emit_audit(
                intent=intent,
                decision=decision,
                platform=gate.platform,
                model=gate.model,
                out_file=gate.audit_file,
            )

            if decision.blocked:
                raise BlockedByGate(
                    f"Blocked by gate: {decision.reason_code}",
                    decision_reason=decision.reason,
                    reason_code=decision.reason_code,
                )

            return func(*args, **kwargs)

        return cast(F, wrapper)
    return decorator
