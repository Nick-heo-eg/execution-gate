from __future__ import annotations

from typing import Any, Dict, Optional

from .decision import ActionEnvelope, Decision  # noqa: F401 (re-exported)
from .policy import Policy, PolicyError, load_policy
from .telemetry import eb_evaluate_span, set_decision_attributes


class Gate:
    """
    Execution Boundary Core Spec v0.1 — reference implementation.

    Flow:
      ActionEnvelope → Evaluator → Decision → Ledger → Runtime (ALLOW only)

    Fail-closed: any evaluation failure produces DENY.
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

    def evaluate(self, envelope: ActionEnvelope) -> Decision:
        """
        Deterministic evaluation. Side-effect free.
        Returns Decision with result ALLOW | DENY | HOLD.
        Never executes the action.

        Emits eb.evaluate OTel span if opentelemetry-api is installed.
        eb.* attributes: eb.envelope_id, eb.decision, eb.reason_code, eb.ledger_commit, eb.proof_hash
        """
        with eb_evaluate_span(
            envelope_id=envelope.action_id,
            action_type=envelope.action_type,
        ) as span:
            decision = self._evaluate_inner(envelope)
            set_decision_attributes(span, decision)
            return decision

    def _evaluate_inner(self, envelope: ActionEnvelope) -> Decision:
        """Pure evaluation logic. No observability concerns."""
        policy = self._load_policy_fail_closed()
        if policy is None:
            return Decision.deny(
                envelope.action_id,
                "Policy unavailable (fail-closed)",
                reason_code="POLICY_UNAVAILABLE",
            )

        rule = policy.find_rule(envelope.action_type)
        if rule is None:
            return Decision.deny(
                envelope.action_id,
                f"Action not allowed (no rule): {envelope.action_type}",
                reason_code="NO_RULE",
            )

        if rule.allowed is False:
            return Decision.deny(
                envelope.action_id,
                f"Action explicitly denied: {envelope.action_type}",
                reason_code="DENY_RULE",
            )

        if rule.max_amount is not None:
            amount = envelope.parameters.get("amount")
            if not isinstance(amount, (int, float)):
                return Decision.deny(
                    envelope.action_id,
                    "amount required for this action",
                    reason_code="MISSING_AMOUNT",
                )
            if float(amount) > float(rule.max_amount):
                return Decision.deny(
                    envelope.action_id,
                    f"amount exceeds max_amount ({amount} > {rule.max_amount})",
                    reason_code="AMOUNT_EXCEEDS_LIMIT",
                    details={"amount": float(amount), "max_amount": float(rule.max_amount)},
                )

        return Decision.allow(envelope.action_id)

    def check(self, intent: Dict[str, Any]) -> Decision:
        """
        Compatibility entry point. Accepts legacy intent dict.
        Builds ActionEnvelope internally, then evaluates.
        """
        if not isinstance(intent, dict):
            dummy = ActionEnvelope.build("__invalid__", "__invalid__", {})
            return Decision.deny(dummy.action_id, "Intent must be a mapping", reason_code="INVALID_INTENT")

        action = intent.get("action")
        if not isinstance(action, str) or not action.strip():
            dummy = ActionEnvelope.build("__invalid__", "__invalid__", {})
            return Decision.deny(dummy.action_id, "Intent.action is required", reason_code="INVALID_INTENT")

        metadata = intent.get("metadata") or {}
        if not isinstance(metadata, dict):
            dummy = ActionEnvelope.build(str(action).strip(), "__invalid__", {})
            return Decision.deny(dummy.action_id, "Intent.metadata must be a mapping", reason_code="INVALID_INTENT")

        envelope = ActionEnvelope.build(
            action_type=action.strip(),
            resource=intent.get("resource", "__unspecified__"),
            parameters=metadata,
        )

        return self.evaluate(envelope)
