from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_proof_hash(decision_id: str, action_id: str, result: str, timestamp: str) -> str:
    raw = f"{decision_id}{action_id}{result}{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class ActionEnvelope:
    """Structured, immutable representation of a proposed action."""
    action_id: str
    action_type: str
    resource: str
    parameters: Dict[str, Any]
    context_hash: str
    timestamp: str

    @staticmethod
    def build(action_type: str, resource: str, parameters: Dict[str, Any]) -> "ActionEnvelope":
        action_id = str(uuid.uuid4())
        timestamp = _now_iso()
        context_hash = hashlib.sha256(
            f"{action_type}{resource}{timestamp}".encode()
        ).hexdigest()
        return ActionEnvelope(
            action_id=action_id,
            action_type=action_type,
            resource=resource,
            parameters=parameters,
            context_hash=context_hash,
            timestamp=timestamp,
        )


@dataclass(frozen=True)
class Decision:
    """
    Output of the Evaluator. Conforms to Execution Boundary Core Spec v0.1.
    result: ALLOW | DENY | HOLD
    Only ALLOW permits execution.
    """
    decision_id: str
    action_id: str
    result: str  # "ALLOW" | "DENY" | "HOLD"
    reason_code: str
    authority_token: str
    proof_hash: str
    timestamp: str
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    @property
    def allowed(self) -> bool:
        return self.result == "ALLOW"

    @staticmethod
    def _make(
        action_id: str,
        result: str,
        reason_code: str,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        authority_token: str = "execution-gate/v0.2",
    ) -> "Decision":
        decision_id = str(uuid.uuid4())
        timestamp = _now_iso()
        proof_hash = _compute_proof_hash(decision_id, action_id, result, timestamp)
        return Decision(
            decision_id=decision_id,
            action_id=action_id,
            result=result,
            reason_code=reason_code,
            authority_token=authority_token,
            proof_hash=proof_hash,
            timestamp=timestamp,
            reason=reason,
            details=details,
        )

    @staticmethod
    def allow(action_id: str) -> "Decision":
        return Decision._make(action_id=action_id, result="ALLOW", reason_code="POLICY_ALLOW")

    @staticmethod
    def deny(action_id: str, reason: str, reason_code: str = "POLICY_DENY",
             details: Optional[Dict[str, Any]] = None) -> "Decision":
        return Decision._make(
            action_id=action_id, result="DENY",
            reason_code=reason_code, reason=reason, details=details,
        )

    @staticmethod
    def hold(action_id: str, reason: str, reason_code: str = "HOLD") -> "Decision":
        return Decision._make(action_id=action_id, result="HOLD",
                              reason_code=reason_code, reason=reason)
