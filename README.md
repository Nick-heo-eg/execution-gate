# execution-gate (v0.3)

Reference implementation of [Execution Boundary Core Spec v0.1](https://github.com/Nick-heo-eg/execution-boundary-core-spec) (commit: `47588ff`).

Execution does not occur by default. An explicit `ALLOW` decision is required before any side-effect runs.

---

## Spec Conformance

| Core Spec requirement | Status |
|---|---|
| ActionEnvelope (action_id, context_hash) | ✓ |
| Evaluator — side-effect free | ✓ |
| Decision (decision_id, result, authority_token, proof_hash) | ✓ |
| result: ALLOW \| DENY \| HOLD | ✓ |
| Ledger append — DENY recorded | ✓ |
| Fail-closed on evaluator failure | ✓ |
| Runtime executes only on ALLOW | ✓ |

Schema reference: [`spec/`](https://github.com/Nick-heo-eg/execution-boundary-core-spec/tree/main/spec)

---

## Quickstart

```bash
git clone https://github.com/Nick-heo-eg/execution-gate.git
cd execution-gate
pip install -e .
```

---

## Usage

### Envelope + Evaluate (explicit flow)

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

  - action: send_email
    allowed: true
```

---

## Decision Output

Every evaluation produces a Decision object conforming to Core Spec:

```json
{
  "decision_id": "uuid",
  "action_id": "uuid",
  "result": "DENY",
  "reason_code": "AMOUNT_EXCEEDS_LIMIT",
  "authority_token": "execution-gate/v0.3",
  "proof_hash": "sha256...",
  "timestamp": "2026-03-03T00:00:00+00:00"
}
```

DENY decisions are recorded in the ledger. Absence of execution is provable.

---

## Fail-Closed Behavior

| Condition | Decision |
|---|---|
| Policy file missing | DENY (`POLICY_UNAVAILABLE`) |
| Unknown action | DENY (`NO_RULE`) |
| Rule violation | DENY (`DENY_RULE` / `AMOUNT_EXCEEDS_LIMIT`) |
| Explicit allow rule met | ALLOW |

---

## Observability (optional)

`evaluate()` emits `eb.evaluate` OTel spans when `opentelemetry-api` is installed.
Gate behavior is identical without it — instrumentation is a no-op if OTel is absent.

```bash
pip install execution-gate[otel]
```

Attributes emitted per decision:

| Attribute | Values |
|---|---|
| `eb.decision` | `ALLOW` / `DENY` / `HOLD` |
| `eb.reason_code` | e.g. `AMOUNT_EXCEEDS_LIMIT`, `NO_RULE` |
| `eb.ledger_commit` | `true` / `false` |
| `eb.proof_hash` | first 8 chars of SHA-256 |
| `eb.envelope_id` | UUID (span attribute only — not a metric label) |

Collector topology, tail sampling policy, dashboards, and alerts:
→ [execution-observability-profile](https://github.com/Nick-heo-eg/execution-observability-profile)

---

## Tests

```bash
pytest tests/
```

---

## Design

- Evaluator is a pure function — no side-effects, no execution
- Decision is immutable once produced
- Ledger append is unconditional — DENY entries included
- Runtime blocked unless `decision.result == "ALLOW"`
- OTel instrumentation isolated in `gate/instrumentation/` — never imported by core evaluation path

---

## Benchmark

Naive baseline (keyword filter + known-bad list) vs Echo Gate — 24 cases across normal, risky, and ambiguous inputs.

| Metric | Naive Baseline | Echo Gate |
|---|---|---|
| **False Negative Rate** | **78.6%** (11/14 risky cases missed) | **0.0%** |
| Accuracy | 54.2% | 95.8% |

The naive baseline caught only the actions it explicitly knew about. Everything else passed through.  
Echo Gate caught all risky cases deterministically — including unknown actions, ambiguous instructions, and incomplete context.

> The baseline represents a minimal heuristic filter, not a production-grade safety system.  
> Full benchmark dataset and evaluation script are reproducible on request.

### Tradeoff

The system prioritizes eliminating false negatives.

- False negative rate: 0.0%
- False positive: 1 case (known limitation — action-level policy does not yet control resource paths)

This reflects a safety-first design: over-blocking is acceptable and tunable. Under-blocking is not.

### Representative Cases

**Case 1 — Limit violation**

```
Input:    transfer_money, amount=5000  (policy limit: 1000)
Baseline: ALLOW  — "no known risk detected"
Echo:     DENY   — AMOUNT_EXCEEDS_LIMIT
```

**Case 2 — Deployment without approval**

```
Input:    service.deploy, resource=prod-api
Baseline: ALLOW  — action not in deny list
Echo:     HOLD   — explicit approval required (HOLD_RULE)
```

**Case 3 — Unknown action (fail-closed)**

```
Input:    unknown_action, resource=mystery-system
Baseline: ALLOW  — no rule matched, default pass
Echo:     DENY   — no rule matched, default deny (NO_RULE)
```

The structural difference: baseline is fail-open. Echo Gate is fail-closed.  
When no rule exists, baseline executes. Echo Gate does not.

---

## License

MIT
