import tempfile
from gate import Firewall

def write_policy(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml")
    f.write(content)
    f.close()
    return f.name

def test_fail_closed_policy_missing():
    fw = Firewall(policy_path="/no/such/file.yaml")
    d = fw.check({"actor":"a","action":"send_email","metadata":{}})
    assert d.status == "BLOCK"
    assert d.reason_code == "POLICY_UNAVAILABLE"

def test_unknown_action_blocks():
    path = write_policy("rules:\n  - action: send_email\n    allowed: true\n")
    fw = Firewall(policy_path=path)
    d = fw.check({"actor":"a","action":"unknown_action","metadata":{}})
    assert d.status == "BLOCK"
    assert d.reason_code == "NO_RULE"

def test_max_amount_blocks():
    path = write_policy("rules:\n  - action: transfer_money\n    max_amount: 1000\n")
    fw = Firewall(policy_path=path)
    d = fw.check({"actor":"a","action":"transfer_money","metadata":{"amount":5000}})
    assert d.status == "BLOCK"
    assert d.reason_code == "AMOUNT_EXCEEDS_LIMIT"

def test_allow():
    path = write_policy("rules:\n  - action: send_email\n    allowed: true\n")
    fw = Firewall(policy_path=path)
    d = fw.check({"actor":"a","action":"send_email","metadata":{}})
    assert d.status == "ALLOW"
