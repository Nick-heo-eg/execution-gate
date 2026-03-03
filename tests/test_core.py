import tempfile
from gate import Gate
from gate.decision import ActionEnvelope


def write_policy(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml")
    f.write(content)
    f.close()
    return f.name


def test_fail_closed_policy_missing():
    gate = Gate(policy_path="/no/such/file.yaml")
    d = gate.check({"actor": "a", "action": "send_email", "metadata": {}})
    assert d.result == "DENY"
    assert d.reason_code == "POLICY_UNAVAILABLE"
    assert d.decision_id
    assert d.proof_hash


def test_unknown_action_denied():
    path = write_policy("rules:\n  - action: send_email\n    allowed: true\n")
    gate = Gate(policy_path=path)
    d = gate.check({"actor": "a", "action": "unknown_action", "metadata": {}})
    assert d.result == "DENY"
    assert d.reason_code == "NO_RULE"


def test_max_amount_denied():
    path = write_policy("rules:\n  - action: transfer_money\n    max_amount: 1000\n")
    gate = Gate(policy_path=path)
    d = gate.check({"actor": "a", "action": "transfer_money", "metadata": {"amount": 5000}})
    assert d.result == "DENY"
    assert d.reason_code == "AMOUNT_EXCEEDS_LIMIT"


def test_allow():
    path = write_policy("rules:\n  - action: send_email\n    allowed: true\n")
    gate = Gate(policy_path=path)
    d = gate.check({"actor": "a", "action": "send_email", "metadata": {}})
    assert d.result == "ALLOW"
    assert d.allowed is True
    assert d.decision_id
    assert d.action_id
    assert d.proof_hash


def test_envelope_evaluate():
    path = write_policy("rules:\n  - action: file.write\n    allowed: true\n")
    gate = Gate(policy_path=path)
    envelope = ActionEnvelope.build(
        action_type="file.write",
        resource="/tmp/test.txt",
        parameters={"content": "hello"},
    )
    d = gate.evaluate(envelope)
    assert d.result == "ALLOW"
    assert d.action_id == envelope.action_id
    assert d.proof_hash


def test_deny_produces_proof_hash():
    gate = Gate(policy_path="/no/such/file.yaml")
    envelope = ActionEnvelope.build("transfer_money", "bank/account", {"amount": 9999})
    d = gate.evaluate(envelope)
    assert d.result == "DENY"
    assert d.proof_hash
    assert d.decision_id
    assert d.authority_token
