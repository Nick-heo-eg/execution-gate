"""
gate/instruction_normalizer.py
Policy Adapter Layer (구 Pre-Gate Normalization)

스코프 명확화 (Atlas 143, 2026-04-17):
  이 모듈의 역할은 LLM을 위한 rewrite가 아니라
  "입력을 Gate policy 구조에 맞추는 것"이다.

  IN:  ActionEnvelope.parameters["instruction"] — 자연어/자유형식 텍스트
  OUT: NormalizedInstruction
         - explicit_deny   → Gate: DENY
         - ambiguity_flag  → Gate: policy에 따라 결정 (이 모듈은 분류만)

제거된 항목 (Atlas 143):
  - TOKEN_DRIFT_GUARD   → 비용/지연 문제. Gate scope 아님. Observability 레이어 소관.
  - REASONING_EFFORT_LOCK → API 호출 파라미터. Gate가 hook할 수 없음. LLM Proxy화 위험.

남은 항목 (Gate scope에 해당하는 것만):
  1. EXPLICIT_DENY    — 명시적 위험 패턴 포함 여부 (rm -rf, drop table 등)
                        → 입력 자체가 위험. Gate가 반드시 차단해야 함.
  2. AMBIGUITY_FLAG   — 모호한 표현 포함 여부 (가능하면, 알아서, 적당히)
                        → Gate policy에 ambiguous_instruction rule이 있으면 매칭.
                        → 이 모듈은 flag만 세움. 차단 결정은 Gate 소관.

DESIGN 원칙:
  - 이 모듈은 분류(classification)만 한다.
  - pre_gate_hint는 Gate의 정책 판단을 돕는 signal이지 강제가 아니다.
  - EXPLICIT_DENY만 예외: 입력 자체가 위험 패턴이면 hint=DENY가 맞다.
    (policy가 없어도 "rm -rf"는 차단해야 한다는 불변 규칙)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── 명시적 위험 패턴 (입력 자체가 위험 — policy 무관하게 차단) ──────────────────

_EXPLICIT_DENY_PATTERNS = [
    r"rm\s+-rf",
    r"drop\s+table",
    r"delete\s+all",
    r"force\s+push",
    r"--no-verify",
    r"sudo\s+rm",
    r"truncate\s+database",
]

# ── 모호한 표현 (policy 판단 필요) ───────────────────────────────────────────────

_AMBIGUOUS_TRIGGERS = [
    "가능하면", "적당히", "대충", "알아서", "적절히", "웬만하면",
    "if possible", "roughly", "as you see fit", "use your judgment",
    "when appropriate", "maybe", "possibly", "sort of",
]


@dataclass
class NormalizedInstruction:
    original: str
    explicit_constraints: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    # 위험 패턴
    explicit_deny: bool = False
    deny_pattern: str = ""
    # 모호성 (Gate policy가 결정)
    ambiguity_detected: bool = False
    ambiguous_terms: List[str] = field(default_factory=list)
    # Gate signal: PROCEED / DENY
    # HOLD는 Gate policy 매칭 결과. 이 모듈은 hint만 제공.
    pre_gate_hint: str = "PROCEED"


def normalize(
    text: str,
    context: Optional[Dict[str, Any]] = None,
) -> NormalizedInstruction:
    """
    instruction 텍스트 → NormalizedInstruction.
    분류만 수행. 차단 결정은 Gate 소관.
    """
    result = NormalizedInstruction(original=text)
    tl = text.lower()

    # 1. EXPLICIT_DENY — 입력 자체가 위험 패턴 (불변 규칙)
    for pat in _EXPLICIT_DENY_PATTERNS:
        if re.search(pat, tl):
            result.explicit_deny = True
            result.deny_pattern = pat
            result.risk_flags.append(f"EXPLICIT_DENY: {pat}")
            result.pre_gate_hint = "DENY"
            break

    # 2. AMBIGUITY_FLAG — 모호한 표현 감지 (Gate policy가 결정)
    found = [term for term in _AMBIGUOUS_TRIGGERS if term in tl]
    if found:
        result.ambiguity_detected = True
        result.ambiguous_terms = found
        result.risk_flags.append(f"AMBIGUITY: {found}")
        # hint는 PROCEED 유지. Gate policy에 rule이 있으면 HOLD로 처리.
        # (단, explicit_deny가 없을 때만 — 이미 DENY면 더 강한 결과 유지)

    # 명시적 제약 추출 (policy 매칭용)
    for pat in [r"반드시\s+\S+", r"금지\s*[:：]?\s*\S+",
                r"must\s+\w+", r"never\s+\w+", r"do not\s+\w+"]:
        result.explicit_constraints.extend(re.findall(pat, tl))

    return result


def summary(ni: NormalizedInstruction) -> str:
    lines = [
        "[PolicyAdapter]",
        f"  hint            : {ni.pre_gate_hint}",
        f"  explicit_deny   : {ni.explicit_deny}  {ni.deny_pattern or ''}",
        f"  ambiguity       : {ni.ambiguity_detected}  {ni.ambiguous_terms or ''}",
        f"  risk_flags      : {ni.risk_flags}",
        f"  constraints     : {ni.explicit_constraints}",
    ]
    return "\n".join(lines)
