# execution-gate

AI agents execute actions. Most systems cannot deterministically stop unsafe execution.

Prevents unsafe execution before it happens.

---

## Benchmark

Naive baseline (keyword filter + known-bad list) vs execution-gate — 24 cases across normal, risky, and ambiguous inputs.

| Metric | Naive Baseline | execution-gate |
|---|---|---|
| **False Negative Rate** | **78.6%** (11/14 risky cases missed) | **0.0%** |
| Accuracy | 54.2% | 95.8% |

The naive baseline caught only the actions it explicitly knew about. Everything else passed through.  
execution-gate caught all risky cases deterministically — unknown actions, ambiguous instructions, incomplete context.

> The baseline represents a minimal heuristic filter, not a production-grade safety system.  
> Full benchmark dataset and evaluation script are reproducible on request.

### Tradeoff

- False negative rate: 0.0%
- False positive: 1 case (known limitation — action-level policy does not yet control resource paths)

Safety-first design: over-blocking is acceptable and tunable. Under-blocking is not.

### Representative Cases

**Case 1 — Limit violation**

```
Input:    transfer_money, amount=5000  (policy limit: 1000)
Baseline: ALLOW  — "no known risk detected"
Gate:     DENY   — AMOUNT_EXCEEDS_LIMIT
```

**Case 2 — Deployment without approval**

```
Input:    service.deploy, resource=prod-api
Baseline: ALLOW  — action not in deny list
Gate:     HOLD   — explicit approval required (HOLD_RULE)
```

**Case 3 — Unknown action**

```
Input:    unknown_action, resource=mystery-system
Baseline: ALLOW  — no rule matched, default pass
Gate:     DENY   — no rule matched, default deny (NO_RULE)
```

Baseline is fail-open. execution-gate is fail-closed.  
When no rule exists, baseline executes. execution-gate does not.

---

## How it works

- Policy-driven: YAML rules define what is allowed, held, or denied
- Fail-closed: no matching rule → DENY (not ALLOW)
- Deterministic: same input always produces same decision
- Every decision produces a tamper-evident proof record (SHA-256)

---

## Quickstart

```bash
git clone https://github.com/Nick-heo-eg/execution-gate.git
cd execution-gate
pip install -e .
```

---

## Usage

### Evaluate an action

```python
from gate import Gate, ActionEnvelope

gate = Gate(policy_path="policy.yaml", platform="my-app")

envelope = ActionEnvelope.build(
    action_type="transfer_money",
    resource="bank/account",
    parameters={"amount": 500},
)

decision = gate.evaluate(envelope)
print(decision.result)        # "ALLOW" or "DENY"
print(decision.proof_hash)    # SHA-256 verifiable record
print(decision.decision_id)   # UUID
```

### Decorator enforcement

```python
from gate import Gate, enforce, BlockedByGate

gate = Gate(policy_path="policy.yaml", platform="my-app")

@enforce(gate, intent_builder=lambda amt: {
    "action": "transfer_money",
    "metadata": {"amount": amt},
})
def transfer_money(amt: float):
    return f"Transferred: {amt}"

try:
    transfer_money(5000)
except BlockedByGate as e:
    print(e.reason_code)  # "AMOUNT_EXCEEDS_LIMIT"
```

---

## Policy

```yaml
rules:
  - action: delete_database
    allowed: false

  - action: transfer_money
    max_amount: 1000

  - action: service.deploy
    hold: true        # requires explicit approval

  - action: send_email
    allowed: true
```

---

## Decision Output

Every evaluation produces an immutable Decision:

```json
{
  "decision_id": "uuid",
  "action_id": "uuid",
  "result": "DENY",
  "reason_code": "AMOUNT_EXCEEDS_LIMIT",
  "proof_hash": "sha256...",
  "timestamp": "2026-03-03T00:00:00+00:00"
}
```

DENY and HOLD decisions are recorded in the ledger. Absence of execution is provable.

---

## Fail-Closed Behavior

| Condition | Decision |
|---|---|
| Policy file missing | DENY (`POLICY_UNAVAILABLE`) |
| Unknown action | DENY (`NO_RULE`) |
| Rule violation | DENY (`DENY_RULE`) |
| Requires approval | HOLD (`HOLD_RULE`) |
| Explicit allow rule met | ALLOW |

---

## Observability (optional)

`evaluate()` emits `eb.evaluate` OTel spans when `opentelemetry-api` is installed.
Gate behavior is identical without it.

```bash
pip install execution-gate[otel]
```

| Attribute | Values |
|---|---|
| `eb.decision` | `ALLOW` / `DENY` / `HOLD` |
| `eb.reason_code` | e.g. `AMOUNT_EXCEEDS_LIMIT`, `NO_RULE` |
| `eb.proof_hash` | first 8 chars of SHA-256 |

---

## Tests

```bash
pytest tests/
```

---

## Spec

Reference implementation of [Execution Boundary Core Spec v0.1](https://github.com/Nick-heo-eg/execution-boundary-core-spec).

---

## License

MIT
