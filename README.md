# Deterministic Execution Gate (v0.1)

Most agent frameworks let execution happen by default.
This library requires an explicit ALLOW before any side-effect runs.

---

## Quickstart (60 seconds)

```bash
git clone https://github.com/Nick-heo-eg/execution-gate.git
cd execution-gate
pip install -e .
gate-demo
```

You'll see:
- ✅ Small transfer → ALLOW
- ❌ Large transfer → BLOCK (exceeds limit)
- ❌ Delete database → BLOCK (explicitly denied)
- ❌ Unknown action → BLOCK (no rule)

All decisions include structured JSON audit logs.

---

## Features

- **Fail-closed by default**: Missing policy → BLOCK, Unknown action → BLOCK
- **Deterministic decisions**: ALLOW or BLOCK, no probabilistic output
- **YAML-based policy rules**: Simple, readable configuration
- **Structured audit logging**: JSON format for observability
- **Decorator-based enforcement**: Block execution before it happens

---

## Install

```bash
pip install -e .
```

---

## Example Usage

```python
from gate import Gate, enforce, BlockedByGate

# Initialize with policy file
gate = Gate(policy_path="policy.yaml", platform="my-app")

# Check intent manually
decision = gate.check({
    "actor": "agent",
    "action": "transfer_money",
    "metadata": {"amount": 500}
})

print(decision.status)  # "ALLOW" or "BLOCK"

# Or use decorator to enforce
@enforce(gate, intent_builder=lambda amt: {
    "actor": "agent",
    "action": "transfer_money",
    "metadata": {"amount": amt}
})
def transfer_money(amt: float):
    return f"Transferred: {amt}"

try:
    transfer_money(5000)  # Blocked if exceeds policy limit
except BlockedByGate as e:
    print(f"Blocked: {e.reason_code}")
```

---

## Policy Example

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

## Safety Model

| Condition | Decision |
|-----------|----------|
| Missing policy file | BLOCK |
| Unknown action | BLOCK |
| Rule violation | BLOCK |
| Explicit allow rule | ALLOW |

**Fail-closed by default.**

---

## Tests

```bash
pip install pytest
pytest
```

All tests verify fail-closed behavior and deterministic enforcement.

---

## Design Principles

- **Deterministic**: No LLM judgment, no probabilistic guardrails
- **Pre-execution**: Decision happens before side-effects
- **Observable**: Structured logs for audit and monitoring
- **Minimal**: Single-purpose library, no framework lock-in

---

## Examples

See `examples/` for runnable scripts, including a minimal agent demo.

---

## License

MIT
