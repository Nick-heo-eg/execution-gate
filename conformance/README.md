# Gate Conformance Harness

Automated enforcement of Execution Boundary Gate invariants.

**The gate controls execution. This harness proves it does.**

---

## Invariants Enforced

| # | Invariant | Test file |
|---|---|---|
| 1 | Fail-Closed — gate MUST produce DENY when policy is unavailable | `test_fail_closed.py` |
| 2 | Decision Completeness — all required fields present on every Decision | `test_decision_completeness.py` |
| 3 | Proof Hash Integrity — `proof_hash == sha256(decision_id + action_id + result + timestamp)` | `test_proof_hash_integrity.py` |
| 4 | No Execution on DENY/HOLD — `allowed == True` only when `result == "ALLOW"` | `test_execution_gate.py` |

---

## Run

```bash
pip install -e .
pip install -r conformance/requirements.txt
pytest conformance/tests/ -v
```

No Docker. No network. Completes in under 10 seconds.

---

## Structure

```
conformance/
  README.md              ← this file
  requirements.txt       ← pytest + jsonschema + pyyaml
  fixtures/
    decisions/
      allow_decision.json          ← valid ALLOW decision
      deny_decision.json           ← valid DENY decision
      deny_missing_proof.json      ← INVALID: proof_hash absent (schema violation)
      deny_wrong_proof.json        ← INVALID: proof_hash value incorrect (integrity violation)
  tests/
    conftest.py
    test_fail_closed.py
    test_decision_completeness.py
    test_proof_hash_integrity.py
    test_execution_gate.py
```

---

## Fixture Convention

Valid fixtures: assert invariants pass.
Invalid fixtures (descriptive suffix): used in meta-tests to verify detection logic.
Invalid fixtures are never in the normal parametrize list.

---

## Relationship to execution-observability-profile

These harnesses enforce different layers:

| Harness | Enforces |
|---|---|
| execution-gate conformance | How Decisions are **produced** |
| execution-observability-profile conformance | How Decisions are **observed** |

Together they close the loop: Decision production → OTel span → Jaeger.
