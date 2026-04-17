"""
gate/context_integrity.py
Context Integrity Check — Silent Constraint Drop 방어

배경 (Atlas 142→143):
  Opus 4.7+ 파일시스템 기반 외부 메모리 구조.
  retrieval 실패 → policy/constraints/authority가 이번 턴 context에 없는 채로
  모델 판단 → 기존보다 위험 (모델은 "없는 줄 알고" 실행함).

  기존: context에 있었음 → 모델이 무시해야만 문제
  지금: 아예 안 들어옴 → 모델은 모른다

설계 원칙 (Atlas 143 수정):
  이 모듈은 "분류(classification)만" 한다.
  severity → HOLD/ALLOW 변환은 Gate core.py 소관.
  위반: Integrity Check가 직접 차단 → risk logic 분산 (Gate 철학 위반)
  준수: Integrity Check가 severity 반환 → Gate가 severity 맵 기반 결정

흐름:
  [External Memory / Retrieval]
    ↓
  [Context Integrity Check]  ← 여기: 분류만
    ↓
  [ActionEnvelope]
    ↓
  [Gate]  ← 여기: 결정
    ↓
  [Execution]

REQUIRED_CONTEXT 항목 및 severity:
  policy      — CRITICAL  실행 정책 (없으면 Gate 판단 불가)
  constraints — HIGH      명시적 제약 (없으면 Policy Adapter 의미 없음)
  authority   — MEDIUM    실행 권한 (없으면 authorization 우회 가능)

Gate severity 맵 (core.py에서 소유):
  CRITICAL → HOLD
  HIGH     → HOLD
  MEDIUM   → HOLD
  (맵 자체는 Gate가 변경 가능 — 이 파일 수정 불필요)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


STALE_CONTEXT_SECONDS = 300

REQUIRED_CONTEXT_SPEC = [
    {
        "key": "policy",
        "severity": "CRITICAL",
        "description": "실행 정책",
        "aliases": ["policy_path", "policy_ref", "policy_content"],
    },
    {
        "key": "constraints",
        "severity": "HIGH",
        "description": "명시적 제약",
        "aliases": ["constraint", "rules", "explicit_constraints"],
    },
    {
        "key": "authority",
        "severity": "MEDIUM",
        "description": "실행 권한",
        "aliases": ["authority_token", "auth", "authorization"],
    },
]

ADVISORY_CONTEXT_SPEC = [
    {"key": "session_id",           "description": "세션 추적"},
    {"key": "retrieval_timestamp",  "description": "retrieval 시점 (stale 감지용)"},
]


@dataclass
class IntegrityResult:
    """
    분류 결과만 담는다. 차단/통과 결정은 포함하지 않는다.
    Gate가 severity_level을 읽어 결정한다.
    """
    # 가장 높은 누락 severity ("" = 모두 있음)
    severity_level: str = ""              # "" / MEDIUM / HIGH / CRITICAL
    missing: List[str] = field(default_factory=list)    # 누락된 key 목록
    stale: bool = False
    advisories: List[str] = field(default_factory=list)
    # 진단용 — Gate가 결정에 사용할 reason
    reason: str = ""


def _find(key: str, aliases: List[str], ctx: Dict[str, Any]) -> bool:
    for k in [key] + aliases:
        v = ctx.get(k)
        if v is not None and v != "" and v != {} and v != []:
            return True
    return False


def check(
    context: Dict[str, Any],
    skip_keys: Optional[List[str]] = None,
) -> IntegrityResult:
    """
    context dict → IntegrityResult (분류만).
    차단 결정을 하지 않는다.
    """
    skip = set(skip_keys or [])
    result = IntegrityResult()

    # severity 우선순위 맵
    sev_rank = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1}
    highest_sev = ""
    highest_rank = 0

    for spec in REQUIRED_CONTEXT_SPEC:
        key = spec["key"]
        if key in skip:
            continue
        if not _find(key, spec["aliases"], context):
            result.missing.append(key)
            sev = spec["severity"]
            if sev_rank.get(sev, 0) > highest_rank:
                highest_rank = sev_rank[sev]
                highest_sev = sev

    result.severity_level = highest_sev
    if highest_sev:
        result.reason = f"context 누락: {result.missing} (severity={highest_sev})"

    # stale 감지 (advisory only — 결정은 Gate 소관)
    ts = context.get("retrieval_timestamp")
    if ts is not None:
        try:
            age = time.time() - float(ts)
            if age > STALE_CONTEXT_SECONDS:
                result.stale = True
                result.advisories.append(
                    f"STALE: {int(age)}초 경과 (>{STALE_CONTEXT_SECONDS}s)"
                )
        except (TypeError, ValueError):
            pass

    # advisory
    for spec in ADVISORY_CONTEXT_SPEC:
        key = spec["key"]
        if key not in skip and not _find(key, [], context):
            result.advisories.append(f"ADVISORY: {key} 없음 — {spec['description']}")

    return result


def summary(r: IntegrityResult) -> str:
    status = f"severity={r.severity_level}" if r.severity_level else "OK"
    lines = [f"[ContextIntegrity]  {status}"]
    if r.missing:
        lines.append(f"  missing  : {r.missing}")
    if r.stale:
        lines.append(f"  stale    : yes")
    for adv in r.advisories:
        lines.append(f"  {adv}")
    if r.reason:
        lines.append(f"  reason   : {r.reason}")
    return "\n".join(lines)
