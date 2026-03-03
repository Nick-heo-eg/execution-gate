"""
Invariant 2: Decision Completeness

Every Decision produced by the gate MUST contain all required fields:
  decision_id, action_id, result, reason_code, authority_token, proof_hash, timestamp

This applies to ALL outcomes: ALLOW, DENY, HOLD.
An incomplete Decision cannot be appended to the ledger and cannot be audited.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import jsonschema
import pytest

from gate import Gate
from gate.decision import ActionEnvelope, Decision

REPO_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "spec" / "decision.schema.json"
REQUIRED_FIELDS = ["decision_id", "action_id", "result", "reason_code",
                   "authority_token", "proof_hash", "timestamp"]

VALID_RESULTS = {"ALLOW", "DENY", "HOLD"}


def decision_as_dict(d: Decision) -> dict:
    """Convert Decision dataclass to dict for schema validation."""
    return {
        "decision_id": d.decision_id,
        "action_id": d.action_id,
        "result": d.result,
        "reason_code": d.reason_code,
        "authority_token": d.authority_token,
        "proof_hash": d.proof_hash,
        "timestamp": d.timestamp,
    }


def write_policy(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml")
    f.write(content)
    f.close()
    return f.name


class TestDecisionCompleteness:

    @pytest.fixture
    def schema(self):
        return json.loads(SCHEMA_PATH.read_text())

    def _make_gate(self, policy_content: str) -> Gate:
        return Gate(policy_path=write_policy(policy_content))

    def test_allow_decision_has_all_required_fields(self):
        gate = self._make_gate("rules:\n  - action: send_email\n    allowed: true\n")
        d = gate.check({"action": "send_email", "metadata": {}})
        for field in REQUIRED_FIELDS:
            assert getattr(d, field, None), f"ALLOW decision missing field: {field}"

    def test_deny_decision_has_all_required_fields(self):
        gate = Gate(policy_path="/no/such/file.yaml")
        d = gate.check({"action": "send_email", "metadata": {}})
        for field in REQUIRED_FIELDS:
            assert getattr(d, field, None), f"DENY decision missing field: {field}"

    def test_allow_decision_validates_against_schema(self, schema):
        gate = self._make_gate("rules:\n  - action: read_file\n    allowed: true\n")
        d = gate.check({"action": "read_file", "metadata": {}})
        # Should not raise
        jsonschema.validate(decision_as_dict(d), schema)

    def test_deny_decision_validates_against_schema(self, schema):
        gate = Gate(policy_path="/no/such/file.yaml")
        d = gate.check({"action": "send_email", "metadata": {}})
        jsonschema.validate(decision_as_dict(d), schema)

    def test_deny_rule_decision_validates_against_schema(self, schema):
        gate = self._make_gate("rules:\n  - action: dangerous_action\n    allowed: false\n")
        d = gate.check({"action": "dangerous_action", "metadata": {}})
        assert d.result == "DENY"
        jsonschema.validate(decision_as_dict(d), schema)

    def test_result_is_valid_enum_value(self):
        gate = self._make_gate("rules:\n  - action: send_email\n    allowed: true\n")
        d = gate.check({"action": "send_email", "metadata": {}})
        assert d.result in VALID_RESULTS

    def test_result_is_valid_enum_on_deny(self):
        gate = Gate(policy_path="/no/such/file.yaml")
        d = gate.check({"action": "anything", "metadata": {}})
        assert d.result in VALID_RESULTS

    def test_reason_code_is_nonempty_string(self):
        for policy, action in [
            ("rules:\n  - action: send_email\n    allowed: true\n", "send_email"),
            ("rules:\n  - action: send_email\n    allowed: true\n", "unknown"),
        ]:
            gate = self._make_gate(policy)
            d = gate.check({"action": action, "metadata": {}})
            assert isinstance(d.reason_code, str) and len(d.reason_code) > 0

    def test_fixture_allow_validates_schema(self, schema):
        fixture = json.loads((REPO_ROOT / "conformance" / "fixtures" / "decisions" / "allow_decision.json").read_text())
        jsonschema.validate(fixture, schema)

    def test_fixture_deny_validates_schema(self, schema):
        fixture = json.loads((REPO_ROOT / "conformance" / "fixtures" / "decisions" / "deny_decision.json").read_text())
        jsonschema.validate(fixture, schema)

    def test_fixture_deny_missing_proof_fails_schema(self, schema):
        """Meta-test: fixture without proof_hash must fail schema validation."""
        fixture = json.loads(
            (REPO_ROOT / "conformance" / "fixtures" / "decisions" / "deny_missing_proof.json").read_text()
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(fixture, schema)
