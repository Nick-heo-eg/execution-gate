"""
Invariant 3: Proof Hash Integrity

proof_hash MUST equal sha256(decision_id + action_id + result + timestamp).

This makes every Decision independently verifiable.
A Decision with a mismatched proof_hash cannot be trusted — it may have been
tampered with after evaluation.
"""
from __future__ import annotations

import hashlib
import tempfile

import pytest

from gate import Gate
from gate.decision import ActionEnvelope, Decision


def compute_expected_proof_hash(decision: Decision) -> str:
    raw = f"{decision.decision_id}{decision.action_id}{decision.result}{decision.timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()


def write_policy(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml")
    f.write(content)
    f.close()
    return f.name


class TestProofHashIntegrity:

    def test_allow_proof_hash_matches(self):
        gate = Gate(policy_path=write_policy(
            "rules:\n  - action: send_email\n    allowed: true\n"
        ))
        d = gate.check({"action": "send_email", "metadata": {}})
        expected = compute_expected_proof_hash(d)
        assert d.proof_hash == expected, (
            f"ALLOW proof_hash mismatch: got {d.proof_hash[:16]}..., "
            f"expected {expected[:16]}..."
        )

    def test_deny_proof_hash_matches(self):
        gate = Gate(policy_path="/no/such/file.yaml")
        d = gate.check({"action": "anything", "metadata": {}})
        expected = compute_expected_proof_hash(d)
        assert d.proof_hash == expected, (
            f"DENY proof_hash mismatch: got {d.proof_hash[:16]}..., "
            f"expected {expected[:16]}..."
        )

    def test_proof_hash_matches_for_all_deny_codes(self):
        """All DENY reason_codes must produce a valid proof_hash."""
        policies_and_actions = [
            ("rules:\n  - action: send_email\n    allowed: false\n", "send_email"),
            ("rules:\n  - action: transfer_money\n    max_amount: 100\n", "transfer_money"),
        ]
        metadata_sets = [
            {},                    # missing amount
            {"amount": 9999},      # exceeds limit
        ]
        gate_missing = Gate(policy_path="/no/such/file.yaml")
        for d in [gate_missing.check({"action": "x", "metadata": {}})]:
            assert d.proof_hash == compute_expected_proof_hash(d)

        for (policy, action), metadata in zip(policies_and_actions, metadata_sets):
            gate = Gate(policy_path=write_policy(policy))
            d = gate.check({"action": action, "metadata": metadata})
            assert d.proof_hash == compute_expected_proof_hash(d), (
                f"proof_hash mismatch for reason_code={d.reason_code}"
            )

    def test_proof_hash_is_hex_string(self):
        gate = Gate(policy_path="/no/such/file.yaml")
        d = gate.check({"action": "anything", "metadata": {}})
        assert isinstance(d.proof_hash, str)
        # sha256 hex digest is 64 chars
        assert len(d.proof_hash) == 64
        assert all(c in "0123456789abcdef" for c in d.proof_hash)

    def test_two_decisions_have_different_proof_hashes(self):
        """Different decisions must never share a proof_hash (collision check)."""
        gate = Gate(policy_path="/no/such/file.yaml")
        d1 = gate.check({"action": "action_a", "metadata": {}})
        d2 = gate.check({"action": "action_b", "metadata": {}})
        assert d1.proof_hash != d2.proof_hash, (
            "Two distinct decisions produced the same proof_hash — "
            "decision_id or timestamp collision"
        )

    def test_wrong_proof_hash_fixture_fails_verification(self):
        """Meta-test: a fixture with a known-wrong proof_hash must fail verification."""
        import json
        from pathlib import Path
        REPO_ROOT = Path(__file__).parent.parent.parent
        fixture = json.loads(
            (REPO_ROOT / "conformance" / "fixtures" / "decisions" / "deny_wrong_proof.json").read_text()
        )
        raw = (
            fixture["decision_id"]
            + fixture["action_id"]
            + fixture["result"]
            + fixture["timestamp"]
        )
        expected = hashlib.sha256(raw.encode()).hexdigest()
        assert fixture["proof_hash"] != expected, (
            "deny_wrong_proof.json fixture should have an incorrect proof_hash for this test to be meaningful"
        )
