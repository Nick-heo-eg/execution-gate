from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .decision import Decision


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_audit(
    *,
    intent: Dict[str, Any],
    decision: Decision,
    platform: str,
    model: Optional[str] = None,
    out_file: Optional[str] = None,
) -> None:
    record: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "platform": platform,
        "model": model,
        "intent": intent,
        "decision": {
            "status": decision.status,
            "reason": decision.reason,
            "reason_code": decision.reason_code,
            "details": decision.details,
        },
    }

    line = json.dumps(record, ensure_ascii=False)
    if out_file:
        with open(out_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    else:
        sys.stdout.write(line + "\n")
