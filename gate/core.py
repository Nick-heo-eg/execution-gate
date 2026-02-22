from __future__ import annotations

from typing import Any, Dict, Optional

from .decision import Decision
from .policy import Policy, PolicyError, load_policy


class Firewall:
    """
    v0.1:
      - Decision: ALLOW/BLOCK only
      - Fail-closed by default
    """

    def __init__(
        self,
        *,
        policy_path: str,
        platform: str = "unknown",
        model: Optional[str] = None,
        audit_file: Optional[str] = None,
    ) -> None:
        self.policy_path = policy_path
        self.platform = platform
        self.model = model
        self.audit_file = audit_file

    def _load_policy_fail_closed(self) -> Optional[Policy]:
        try:
            return load_policy(self.policy_path)
        except PolicyError:
            return None

    def check(self, intent: Dict[str, Any]) -> Decision:
        """
        intent minimal schema:
          {
            "actor": "agent|user|system",
            "action": "transfer_money|delete_database|shell.exec|...",
            "metadata": {...}   # optional
          }
        """
        # Validate intent (fail-closed)
        if not isinstance(intent, dict):
            return Decision.block("Intent must be a mapping", reason_code="INVALID_INTENT")

        action = intent.get("action")
        if not isinstance(action, str) or not action.strip():
            return Decision.block("Intent.action is required", reason_code="INVALID_INTENT")

        policy = self._load_policy_fail_closed()
        if policy is None:
            return Decision.block("Policy unavailable (fail-closed)", reason_code="POLICY_UNAVAILABLE")

        rule = policy.find_rule(action.strip())
        if rule is None:
            # Unknown action -> BLOCK (fail-closed)
            return Decision.block(f"Action not allowed (no rule): {action}", reason_code="NO_RULE")

        # Explicit allow/deny
        if rule.allowed is False:
            return Decision.block(f"Action explicitly denied: {action}", reason_code="DENY_RULE")

        # Numeric guard example: max_amount
        # Convention: intent.metadata.amount
        metadata = intent.get("metadata") or {}
        if not isinstance(metadata, dict):
            return Decision.block("Intent.metadata must be a mapping", reason_code="INVALID_INTENT")

        if rule.max_amount is not None:
            amount = metadata.get("amount")
            if not isinstance(amount, (int, float)):
                return Decision.block("amount required for this action", reason_code="MISSING_AMOUNT")
            if float(amount) > float(rule.max_amount):
                return Decision.block(
                    f"amount exceeds max_amount ({amount} > {rule.max_amount})",
                    reason_code="AMOUNT_EXCEEDS_LIMIT",
                    details={"amount": float(amount), "max_amount": float(rule.max_amount)},
                )

        # Default allow if allowed not false and checks passed
        return Decision.allow()
