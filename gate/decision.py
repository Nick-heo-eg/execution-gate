from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any


DecisionStatus = str  # "ALLOW" | "BLOCK" (v0.1)


@dataclass(frozen=True)
class Decision:
    status: DecisionStatus
    reason: Optional[str] = None
    reason_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    @property
    def blocked(self) -> bool:
        return self.status != "ALLOW"

    @staticmethod
    def allow() -> "Decision":
        return Decision(status="ALLOW")

    @staticmethod
    def block(reason: str, reason_code: str = "POLICY_BLOCK", details: Optional[Dict[str, Any]] = None) -> "Decision":
        return Decision(status="BLOCK", reason=reason, reason_code=reason_code, details=details)
