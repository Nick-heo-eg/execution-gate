# Deterministic Execution Firewall (v0.1)

Minimal, vendor-neutral pre-execution control for AI agents.

LLMs are probabilistic.
Production systems cannot be.

This firewall enforces deterministic ALLOW/BLOCK decisions
before any side-effect execution.

---

## Features

- Fail-closed policy engine
- Deterministic ALLOW/BLOCK result
- YAML-based rules
- Structured JSON audit logs
- Decorator-based execution enforcement

---

## Install

```bash
pip install -e .
```

---

## Example

```python
from firewall import Firewall

fw = Firewall(policy_path="policy.yaml")

decision = fw.check({
    "actor": "agent",
    "action": "transfer_money",
    "metadata": {"amount": 500}
})

print(decision.status)
```

---

## Safety Model

* Missing policy → BLOCK
* Unknown action → BLOCK
* Rule violation → BLOCK
* Explicit allow rule → ALLOW

Fail-closed by default.
