"""
Invariant 1: Fail-Closed

The gate MUST produce DENY when policy is unavailable.
It MUST NOT produce ALLOW when policy cannot be loaded.

This is the primary safety invariant. A gate that produces ALLOW
on policy load failure is not an execution gate — it is a pass-through.
"""
from __future__ import annotations

import pytest

from gate import Gate
from gate.decision import ActionEnvelope


class TestFailClosed:
    def test_missing_policy_file_produces_deny(self):
        gate = Gate(policy_path="/no/such/file.yaml")
        d = gate.check({"action": "send_email", "metadata": {}})
        assert d.result == "DENY", "Gate must DENY when policy file is missing"

    def test_missing_policy_reason_code(self):
        gate = Gate(policy_path="/no/such/file.yaml")
        d = gate.check({"action": "send_email", "metadata": {}})
        assert d.reason_code == "POLICY_UNAVAILABLE"

    def test_missing_policy_never_allows(self):
        """allowed property must be False when policy is unavailable."""
        gate = Gate(policy_path="/no/such/file.yaml")
        d = gate.check({"action": "send_email", "metadata": {}})
        assert d.allowed is False

    def test_empty_policy_path_produces_deny(self):
        gate = Gate(policy_path="")
        d = gate.check({"action": "send_email", "metadata": {}})
        assert d.result == "DENY"
        assert d.allowed is False

    def test_corrupt_policy_produces_deny(self, tmp_path):
        bad_policy = tmp_path / "bad.yaml"
        bad_policy.write_text("{{{{ not valid yaml at all")
        gate = Gate(policy_path=str(bad_policy))
        d = gate.check({"action": "send_email", "metadata": {}})
        assert d.result == "DENY"
        assert d.allowed is False

    def test_empty_rules_policy_produces_deny(self, tmp_path):
        bad_policy = tmp_path / "empty_rules.yaml"
        bad_policy.write_text("rules: []\n")
        gate = Gate(policy_path=str(bad_policy))
        d = gate.check({"action": "send_email", "metadata": {}})
        assert d.result == "DENY"

    def test_fail_closed_via_evaluate(self):
        """evaluate() path must also be fail-closed."""
        gate = Gate(policy_path="/no/such/file.yaml")
        envelope = ActionEnvelope.build("send_email", "inbox", {})
        d = gate.evaluate(envelope)
        assert d.result == "DENY"
        assert d.allowed is False

    def test_no_action_in_unknown_policy_state_never_sneaks_allow(self):
        """
        Meta-test: verify the test infrastructure itself.
        A gate with a valid policy CAN produce ALLOW.
        This confirms fail-closed tests above are actually testing failure, not normal behavior.
        """
        import tempfile
        f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml")
        f.write("rules:\n  - action: send_email\n    allowed: true\n")
        f.close()
        gate = Gate(policy_path=f.name)
        d = gate.check({"action": "send_email", "metadata": {}})
        assert d.result == "ALLOW", "Control: valid policy must allow send_email"
