from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, cast

from .core import Firewall
from .logger import emit_audit

F = TypeVar("F", bound=Callable[..., Any])


class BlockedByFirewall(RuntimeError):
    def __init__(self, message: str, *, decision_reason: Optional[str] = None, reason_code: Optional[str] = None) -> None:
        super().__init__(message)
        self.decision_reason = decision_reason
        self.reason_code = reason_code


def enforce(
    firewall: Firewall,
    *,
    intent_builder: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Callable[[F], F]:
    """
    Decorator:
      - builds intent deterministically
      - checks via firewall
      - emits audit
      - blocks by raising BlockedByFirewall

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

            decision = firewall.check(intent)
            emit_audit(
                intent=intent,
                decision=decision,
                platform=firewall.platform,
                model=firewall.model,
                out_file=firewall.audit_file,
            )

            if decision.blocked:
                raise BlockedByFirewall(
                    f"Blocked by firewall: {decision.reason_code}",
                    decision_reason=decision.reason,
                    reason_code=decision.reason_code,
                )

            return func(*args, **kwargs)

        return cast(F, wrapper)
    return decorator
