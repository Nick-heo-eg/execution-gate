from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import os
import yaml


class PolicyError(Exception):
    pass


@dataclass(frozen=True)
class Rule:
    action: str
    allowed: Optional[bool] = None
    max_amount: Optional[float] = None
    hold: Optional[bool] = None


@dataclass(frozen=True)
class Policy:
    rules: List[Rule]

    def find_rule(self, action: str) -> Optional[Rule]:
        for r in self.rules:
            if r.action == action:
                return r
        return None


def load_policy(path: str) -> Policy:
    """
    Fail-closed principle:
    - missing file -> PolicyError
    - parse error -> PolicyError
    - invalid schema -> PolicyError
    Caller decides: PolicyError => BLOCK.
    """
    if not path:
        raise PolicyError("Policy path is empty")

    if not os.path.exists(path):
        raise PolicyError(f"Policy file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception as e:
        raise PolicyError(f"Failed to parse policy YAML: {e}") from e

    if not isinstance(raw, dict):
        raise PolicyError("Policy root must be a mapping")

    rules_raw = raw.get("rules")
    if not isinstance(rules_raw, list) or len(rules_raw) == 0:
        raise PolicyError("Policy must contain non-empty 'rules' list")

    rules: List[Rule] = []
    for idx, rr in enumerate(rules_raw):
        if not isinstance(rr, dict):
            raise PolicyError(f"Rule[{idx}] must be a mapping")

        action = rr.get("action")
        if not isinstance(action, str) or not action.strip():
            raise PolicyError(f"Rule[{idx}] missing/invalid 'action'")

        allowed = rr.get("allowed")
        if allowed is not None and not isinstance(allowed, bool):
            raise PolicyError(f"Rule[{idx}] 'allowed' must be boolean if present")

        max_amount = rr.get("max_amount")
        if max_amount is not None and not isinstance(max_amount, (int, float)):
            raise PolicyError(f"Rule[{idx}] 'max_amount' must be number if present")

        hold = rr.get("hold")
        if hold is not None and not isinstance(hold, bool):
            raise PolicyError(f"Rule[{idx}] 'hold' must be boolean if present")

        rules.append(Rule(action=action.strip(), allowed=allowed, max_amount=float(max_amount) if max_amount is not None else None, hold=hold))

    return Policy(rules=rules)
