from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .decision import Decision, ActionEnvelope


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_audit(
    *,
    envelope: ActionEnvelope,
    decision: Decision,
    platform: str,
    model: Optional[str] = None,
    out_file: Optional[str] = None,
) -> None:
    """
    Append-only ledger write. Records both ALLOW and DENY decisions.
    Conforms to Execution Boundary Core Spec v0.1 — negative proof requirement.
    """
    record: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "platform": platform,
        "model": model,
        "envelope": {
            "action_id": envelope.action_id,
            "action_type": envelope.action_type,
            "resource": envelope.resource,
            "context_hash": envelope.context_hash,
            "timestamp": envelope.timestamp,
        },
        "decision": {
            "decision_id": decision.decision_id,
            "action_id": decision.action_id,
            "result": decision.result,
            "reason_code": decision.reason_code,
            "authority_token": decision.authority_token,
            "proof_hash": decision.proof_hash,
            "timestamp": decision.timestamp,
            "reason": decision.reason,
        },
    }

    line = json.dumps(record, ensure_ascii=False)

    if out_file:
        with open(out_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    else:
        import sys
        sys.stdout.write(line + "\n")
