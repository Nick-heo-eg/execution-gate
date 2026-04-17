"""
gate/impact_resolver.py
Impact Resolver — telemetry → judgment input 변환 레이어

역할:
  metrics(error/latency/traffic/scope) → ImpactResult(level, confidence, signals)
  → ActionEnvelope.parameters["impact"]로 전달
  → Gate core.py가 impact_level 기반으로 HOLD 결정

설계 원칙:
  - deterministic: LLM 없음, threshold 기반
  - impact = f(error_rate, latency, traffic, scope) — metric이 아닌 사용자 영향 함수
  - deploy_event는 위험 가중치가 아니라 원인 태그 (cause, not risk multiplier)
  - baseline 없으면 latency 판단 불가 → NONE (안전 방향)

Impact Level:
  CRITICAL  — 즉각 HOLD 필요
  HIGH      — 조건부 HOLD (traffic_ratio / deploy_event 고려)
  LOW       — 모니터링, 실행 허용
  NONE      — 정상

Gate 연결 규칙 (core.py 소관):
  CRITICAL                          → HOLD
  HIGH + traffic_ratio > 0.5        → HOLD
  HIGH + deploy_related tag         → HOLD
  LOW / NONE                        → policy 그대로
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ── 상수 ──────────────────────────────────────────────────────────────────────

IMPACT_LEVELS = ("NONE", "LOW", "HIGH", "CRITICAL")

# latency baseline 없으면 latency 판단 스킵 (false positive 방지)
_LATENCY_SKIP_IF_NO_BASE = True


# ── 결과 타입 ──────────────────────────────────────────────────────────────────

@dataclass
class ImpactResult:
    impact_level: str = "NONE"          # NONE / LOW / HIGH / CRITICAL
    confidence: float = 1.0             # 0~1 (baseline 없으면 낮아짐)
    signals: List[str] = field(default_factory=list)   # 판단 근거
    deploy_related: bool = False        # deploy_event 연관 여부 (원인 태그)
    # Gate 연결용 요약
    should_hold: bool = False           # Gate가 읽는 최종 신호
    hold_reason: str = ""


# ── 핵심 함수 ─────────────────────────────────────────────────────────────────

def resolve(
    error_rate: float,
    latency_p95: float,
    latency_base: Optional[float] = None,
    traffic_ratio: float = 1.0,
    error_scope: str = "global",        # "global" | "partial" | "endpoint"
    deploy_event: bool = False,
) -> ImpactResult:
    """
    telemetry → ImpactResult.

    Args:
        error_rate      : 에러 비율 (0~1). 예: 0.05 = 5%
        latency_p95     : 현재 p95 응답시간 (ms)
        latency_base    : 기준 p95 (ms). None이면 latency 판단 스킵
        traffic_ratio   : 현재 트래픽 / 평시 트래픽 (0~1+). 예: 0.8 = 평시의 80%
        error_scope     : 에러 범위. "global" > "partial" > "endpoint"
        deploy_event    : 최근 배포 여부 (원인 태그용)
    """
    result = ImpactResult()
    signals: List[str] = []
    confidence = 1.0

    # ── latency 증가율 계산 ────────────────────────────────────────────────────
    latency_increase: Optional[float] = None
    if latency_base is not None and latency_base > 0:
        latency_increase = (latency_p95 - latency_base) / latency_base
    else:
        confidence *= 0.7  # baseline 없으면 latency 판단 불확실
        if _LATENCY_SKIP_IF_NO_BASE:
            signals.append("LATENCY_SKIPPED: no baseline provided")

    # ── CRITICAL 판단 ─────────────────────────────────────────────────────────
    is_critical = False

    # error_scope == global은 traffic 무관하게 즉각 심각
    if error_scope == "global":
        if error_rate > 0.05:
            is_critical = True
            signals.append(f"CRITICAL: global error_rate={error_rate:.1%}")

    # 높은 error_rate + 충분한 트래픽
    if error_rate > 0.10 and traffic_ratio > 0.3:
        is_critical = True
        signals.append(f"CRITICAL: error_rate={error_rate:.1%} traffic={traffic_ratio:.0%}")

    # 높은 latency + 충분한 트래픽
    if latency_increase is not None and latency_increase > 0.6 and traffic_ratio > 0.5:
        is_critical = True
        signals.append(f"CRITICAL: latency+{latency_increase:.0%} traffic={traffic_ratio:.0%}")

    # ── HIGH 판단 ─────────────────────────────────────────────────────────────
    is_high = False

    if not is_critical:
        if error_rate > 0.05 and traffic_ratio > 0.2:
            is_high = True
            signals.append(f"HIGH: error_rate={error_rate:.1%} traffic={traffic_ratio:.0%}")

        if latency_increase is not None and latency_increase > 0.3 and traffic_ratio > 0.3:
            is_high = True
            signals.append(f"HIGH: latency+{latency_increase:.0%} traffic={traffic_ratio:.0%}")

    # ── LOW 판단 ──────────────────────────────────────────────────────────────
    is_low = False

    if not is_critical and not is_high:
        if error_rate > 0.01:
            is_low = True
            signals.append(f"LOW: error_rate={error_rate:.1%}")

        if latency_increase is not None and latency_increase > 0.1:
            is_low = True
            signals.append(f"LOW: latency+{latency_increase:.0%}")

    # ── impact_level 결정 ─────────────────────────────────────────────────────
    if is_critical:
        result.impact_level = "CRITICAL"
    elif is_high:
        result.impact_level = "HIGH"
    elif is_low:
        result.impact_level = "LOW"
    else:
        result.impact_level = "NONE"

    # ── deploy_event: 원인 태그 (위험 가중치 아님) ────────────────────────────
    if deploy_event:
        result.deploy_related = True
        signals.append("DEPLOY_RELATED: recent deploy detected (cause tag, not risk multiplier)")

    # ── Gate 연결: should_hold 결정 ───────────────────────────────────────────
    # HOLD 분기 (명시적 4개):
    #
    #   1. CRITICAL → 무조건 HOLD
    #
    #   2. HIGH + traffic_ratio > 0.5 → HOLD
    #      이유: 트래픽 절반 이상이 영향받고 있음
    #
    #   3. HIGH + deploy_related → HOLD
    #      이유: 배포와 동시 이상 → 원인 확인 전 실행 차단
    #
    #   4. HIGH + error_scope == global → HOLD
    #      이유: global 장애인데 HIGH면 즉시 차단
    #      (CRITICAL 조건은 global + error>0.05. global + error 0.01~0.05는 HIGH에 머무름)
    #
    #   미해당 HIGH (통과):
    #      traffic_ratio ≤ 0.5 + deploy 없음 + partial/endpoint scope
    #      → 영향 범위 제한적, 의도적 통과 (monitor 권장)
    #
    if result.impact_level == "CRITICAL":
        result.should_hold = True
        result.hold_reason = f"Impact CRITICAL — {'; '.join(s for s in signals if 'CRITICAL' in s)}"
    elif result.impact_level == "HIGH" and traffic_ratio > 0.5:
        result.should_hold = True
        result.hold_reason = f"Impact HIGH + high traffic ({traffic_ratio:.0%})"
    elif result.impact_level == "HIGH" and result.deploy_related:
        result.should_hold = True
        result.hold_reason = f"Impact HIGH + deploy_related"
    elif result.impact_level == "HIGH" and error_scope == "global" and error_rate > 0.05:
        result.should_hold = True
        result.hold_reason = f"Impact HIGH + global error scope (error_rate={error_rate:.1%})"
    # else: HIGH지만 traffic 낮고 deploy 없고 partial/endpoint scope → 통과 (의도적)
    #       signals에 기록되므로 외부에서 모니터링 가능
    # 참고: global scope라도 error_rate ≤ 0.05면 LOW → 통과 (global은 CRITICAL 조건에서 이미 처리됨)

    result.signals = signals
    result.confidence = round(confidence, 3)
    return result


def summary(r: ImpactResult) -> str:
    lines = [
        f"[ImpactResolver] level={r.impact_level}  confidence={r.confidence:.0%}",
        f"  should_hold    : {r.should_hold}",
    ]
    if r.hold_reason:
        lines.append(f"  hold_reason    : {r.hold_reason}")
    if r.deploy_related:
        lines.append(f"  deploy_related : yes")
    for s in r.signals:
        lines.append(f"  signal         : {s}")
    return "\n".join(lines)
