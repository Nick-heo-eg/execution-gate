"""
Invariant 4: No Execution on DENY/HOLD

decision.allowed MUST be True before any action is executed.
DENY and HOLD decisions MUST have allowed == False.

This is the enforcement invariant. All other invariants are auditing properties.
This one is the gate itself.
"""
from __future__ import annotations

import tempfile

import pytest

from gate import Gate
from gate.decision import ActionEnvelope, Decision


def write_policy(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml")
    f.write(content)
    f.close()
    return f.name


class TestExecutionGate:

    def test_deny_result_has_allowed_false(self):
        gate = Gate(policy_path="/no/such/file.yaml")
        d = gate.check({"action": "send_email", "metadata": {}})
        assert d.result == "DENY"
        assert d.allowed is False

    def test_allow_result_has_allowed_true(self):
        gate = Gate(policy_path=write_policy(
            "rules:\n  - action: send_email\n    allowed: true\n"
        ))
        d = gate.check({"action": "send_email", "metadata": {}})
        assert d.result == "ALLOW"
        assert d.allowed is True

    def test_no_rule_deny_has_allowed_false(self):
        gate = Gate(policy_path=write_policy(
            "rules:\n  - action: send_email\n    allowed: true\n"
        ))
        d = gate.check({"action": "unknown_action", "metadata": {}})
        assert d.result == "DENY"
        assert d.allowed is False

    def test_explicit_deny_rule_has_allowed_false(self):
        gate = Gate(policy_path=write_policy(
            "rules:\n  - action: dangerous_action\n    allowed: false\n"
        ))
        d = gate.check({"action": "dangerous_action", "metadata": {}})
        assert d.result == "DENY"
        assert d.allowed is False

    def test_amount_exceeds_limit_has_allowed_false(self):
        gate = Gate(policy_path=write_policy(
            "rules:\n  - action: transfer_money\n    max_amount: 1000\n"
        ))
        d = gate.check({"action": "transfer_money", "metadata": {"amount": 9999}})
        assert d.result == "DENY"
        assert d.allowed is False

    def test_only_allow_result_has_allowed_true(self):
        """
        Exhaustive check: for any non-ALLOW result, allowed must be False.
        No partial-ALLOW or ambiguous state is permitted.
        """
        gate_missing = Gate(policy_path="/no/such/file.yaml")
        gate_deny_rule = Gate(policy_path=write_policy(
            "rules:\n  - action: blocked\n    allowed: false\n"
        ))
        gate_allow = Gate(policy_path=write_policy(
            "rules:\n  - action: allowed_action\n    allowed: true\n"
        ))

        deny_cases = [
            gate_missing.check({"action": "x", "metadata": {}}),
            gate_deny_rule.check({"action": "blocked", "metadata": {}}),
            gate_allow.check({"action": "unknown", "metadata": {}}),  # NO_RULE
        ]
        for d in deny_cases:
            assert d.result == "DENY", f"Expected DENY, got {d.result}"
            assert d.allowed is False, (
                f"DENY decision has allowed=True (reason_code={d.reason_code}) — "
                "execution gate is broken"
            )

        allow_cases = [
            gate_allow.check({"action": "allowed_action", "metadata": {}}),
        ]
        for d in allow_cases:
            assert d.result == "ALLOW"
            assert d.allowed is True

    def test_allowed_property_consistent_with_result_string(self):
        """allowed must be exactly (result == 'ALLOW') — no other mapping."""
        gate = Gate(policy_path=write_policy(
            "rules:\n  - action: send_email\n    allowed: true\n"
        ))
        for action, expected_result in [
            ("send_email", "ALLOW"),
            ("not_in_policy", "DENY"),
        ]:
            d = gate.check({"action": action, "metadata": {}})
            assert d.allowed == (d.result == "ALLOW"), (
                f"allowed property inconsistent with result for action={action}"
            )

    def test_evaluate_envelope_deny_has_allowed_false(self):
        """evaluate() path (not check()) must also enforce allowed==False on DENY."""
        gate = Gate(policy_path="/no/such/file.yaml")
        envelope = ActionEnvelope.build("transfer_money", "bank", {"amount": 9999})
        d = gate.evaluate(envelope)
        assert d.result == "DENY"
        assert d.allowed is False

    def test_evaluate_envelope_allow_has_allowed_true(self):
        gate = Gate(policy_path=write_policy(
            "rules:\n  - action: transfer_money\n    max_amount: 10000\n"
        ))
        envelope = ActionEnvelope.build("transfer_money", "bank", {"amount": 100})
        d = gate.evaluate(envelope)
        assert d.result == "ALLOW"
        assert d.allowed is True
