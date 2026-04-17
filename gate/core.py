from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from .decision import ActionEnvelope, Decision  # noqa: F401 (re-exported)
from .policy import Policy, PolicyError, load_policy
from .instruction_normalizer import normalize as _normalize_instruction
from .context_integrity import check as _check_context_integrity
from .impact_resolver import resolve as _resolve_impact


# ---------------------------------------------------------------------------
# Instrumentation loader — complete isolation
#
# Gate NEVER depends on OTel. If anything in the instrumentation path fails
# (import error, init error, tracer error), _load_instrumentation() returns
# no-op stubs. The failure is silently discarded.
#
# Conditions covered:
#   A. opentelemetry-api not installed          → ImportError swallowed
#   B. tracer initialisation failure            → any Exception swallowed
#   C. span attribute set failure               → caught inside set_decision_attributes
#   D. context propagation / export failure     → OTel SDK handles async; never blocks
# ---------------------------------------------------------------------------

@contextmanager
def _null_span(*_: Any, **__: Any) -> Generator[None, None, None]:
    yield None


def _noop(*_: Any, **__: Any) -> None:
    return None


def _load_instrumentation() -> tuple:
    """
    Returns (eb_evaluate_span, set_decision_attributes).
    Returns no-op stubs on any failure — no exception ever escapes.
    """
    try:
        from .instrumentation.otel import eb_evaluate_span, set_decision_attributes
        return eb_evaluate_span, set_decision_attributes
    except Exception:  # noqa: BLE001 — intentional broad catch
        return _null_span, _noop


_eb_evaluate_span, _set_decision_attributes = _load_instrumentation()


class Gate:
    """
    Execution Boundary Core Spec v0.1 — reference implementation.

    Flow:
      ActionEnvelope → Evaluator → Decision → Ledger → Runtime (ALLOW only)

    Fail-closed: any evaluation failure produces DENY.
    OTel instrumentation is optional and fully isolated — gate behavior is
    identical whether opentelemetry-api is installed or not.
    """

    def __init__(
        self,
        *,
        policy_path: str,
        platform: str = "unknown",
        model: Optional[str] = None,
        audit_file: Optional[str] = None,
    ) -> None:
        self.policy_path = policy_path
        self.platform = platform
        self.model = model
        self.audit_file = audit_file

    def _load_policy_fail_closed(self) -> Optional[Policy]:
        try:
            return load_policy(self.policy_path)
        except PolicyError:
            return None

    def evaluate(self, envelope: ActionEnvelope) -> Decision:
        """
        Deterministic evaluation. Side-effect free.
        Returns Decision with result ALLOW | DENY | HOLD.
        Never executes the action.

        Emits eb.evaluate OTel span when opentelemetry-api is installed.
        OTel failure does not affect evaluation result.
        """
        try:
            ctx = _eb_evaluate_span(
                envelope_id=envelope.action_id,
                action_type=envelope.action_type,
            )
        except Exception:  # noqa: BLE001
            ctx = _null_span()

        with ctx as span:
            decision = self._evaluate_inner(envelope)
            try:
                _set_decision_attributes(span, decision)
            except Exception:  # noqa: BLE001
                pass  # span attribute failure never propagates
            return decision

    def _evaluate_inner(self, envelope: ActionEnvelope) -> Decision:
        """Pure evaluation logic. No observability concerns."""

        # ── Impact Resolver (telemetry → judgment input) ─────────────────────
        # envelope.parameters에 "impact" 키가 있으면 Impact Resolver 결과로 해석.
        # 없으면 skip (기존 호환).
        # impact dict 직접 전달 또는 metrics dict 전달 두 가지 모두 지원.
        _impact_params = envelope.parameters.get("impact")
        if isinstance(_impact_params, dict):
            # 이미 resolve된 ImpactResult dict이면 직접 사용
            _impact_level   = _impact_params.get("impact_level", "NONE")
            _impact_hold    = _impact_params.get("should_hold", False)
            _impact_reason  = _impact_params.get("hold_reason", "")
            _traffic_ratio  = _impact_params.get("traffic_ratio", 1.0)
            _deploy_related = _impact_params.get("deploy_related", False)
        else:
            # metrics dict이면 resolve() 호출
            _metrics = envelope.parameters.get("metrics")
            if isinstance(_metrics, dict):
                _ir = _resolve_impact(
                    error_rate    = float(_metrics.get("error_rate", 0.0)),
                    latency_p95   = float(_metrics.get("latency_p95", 0.0)),
                    latency_base  = _metrics.get("latency_base"),
                    traffic_ratio = float(_metrics.get("traffic_ratio", 1.0)),
                    error_scope   = str(_metrics.get("error_scope", "global")),
                    deploy_event  = bool(_metrics.get("deploy_event", False)),
                )
                _impact_level   = _ir.impact_level
                _impact_hold    = _ir.should_hold
                _impact_reason  = _ir.hold_reason
                _traffic_ratio  = float(_metrics.get("traffic_ratio", 1.0))
                _deploy_related = _ir.deploy_related
            else:
                _impact_level = "NONE"
                _impact_hold  = False
                _impact_reason = ""
                _traffic_ratio = 1.0
                _deploy_related = False

        if _impact_hold:
            return Decision.hold(
                envelope.action_id,
                f"Impact resolver: {_impact_reason}",
                reason_code=f"IMPACT_{_impact_level}",
            )
        # ── End Impact Resolver ──────────────────────────────────────────────

        # ── Policy Adapter: instruction normalizer ───────────────────────────
        _raw_instruction = (
            envelope.parameters.get("instruction")
            or envelope.parameters.get("description")
            or ""
        )
        if _raw_instruction:
            _ni = _normalize_instruction(_raw_instruction)
            if _ni.pre_gate_hint == "DENY":
                return Decision.deny(
                    envelope.action_id,
                    f"Policy adapter: explicit deny pattern — {_ni.deny_pattern}",
                    reason_code="EXPLICIT_DENY",
                )
            if _ni.ambiguity_detected:
                try:
                    _p = load_policy(self.policy_path)
                    _amb_rule = _p.find_rule("ambiguous_instruction")
                except Exception:
                    _amb_rule = None
                if _amb_rule and _amb_rule.hold:
                    return Decision.hold(
                        envelope.action_id,
                        f"Policy adapter: ambiguous instruction — {_ni.ambiguous_terms}",
                        reason_code="AMBIGUOUS_INSTRUCTION",
                    )

        # ── Context Integrity Check ──────────────────────────────────────────
        _ctx_map = envelope.parameters.get("context")
        if isinstance(_ctx_map, dict):
            _integrity = _check_context_integrity(
                _ctx_map,
                skip_keys=envelope.parameters.get("context_integrity_skip", []),
            )
            if _integrity.severity_level in {"CRITICAL", "HIGH", "MEDIUM"}:
                return Decision.hold(
                    envelope.action_id,
                    f"Context integrity: {_integrity.reason}",
                    reason_code=f"CONTEXT_INTEGRITY_{_integrity.severity_level}",
                )

        policy = self._load_policy_fail_closed()
        if policy is None:
            return Decision.deny(
                envelope.action_id,
                "Policy unavailable (fail-closed)",
                reason_code="POLICY_UNAVAILABLE",
            )

        rule = policy.find_rule(envelope.action_type)
        if rule is None:
            return Decision.deny(
                envelope.action_id,
                f"Action not allowed (no rule): {envelope.action_type}",
                reason_code="NO_RULE",
            )

        if rule.hold is True:
            return Decision.hold(
                envelope.action_id,
                f"Action requires explicit approval: {envelope.action_type}",
                reason_code="HOLD_RULE",
            )

        if rule.allowed is False:
            return Decision.deny(
                envelope.action_id,
                f"Action explicitly denied: {envelope.action_type}",
                reason_code="DENY_RULE",
            )

        if rule.max_amount is not None:
            amount = envelope.parameters.get("amount")
            if not isinstance(amount, (int, float)):
                return Decision.deny(
                    envelope.action_id,
                    "amount required for this action",
                    reason_code="MISSING_AMOUNT",
                )
            if float(amount) > float(rule.max_amount):
                return Decision.deny(
                    envelope.action_id,
                    f"amount exceeds max_amount ({amount} > {rule.max_amount})",
                    reason_code="AMOUNT_EXCEEDS_LIMIT",
                    details={"amount": float(amount), "max_amount": float(rule.max_amount)},
                )

        return Decision.allow(envelope.action_id)

    def check(self, intent: Dict[str, Any]) -> Decision:
        """
        Compatibility entry point. Accepts legacy intent dict.
        Builds ActionEnvelope internally, then evaluates.
        """
        if not isinstance(intent, dict):
            dummy = ActionEnvelope.build("__invalid__", "__invalid__", {})
            return Decision.deny(dummy.action_id, "Intent must be a mapping", reason_code="INVALID_INTENT")

        action = intent.get("action")
        if not isinstance(action, str) or not action.strip():
            dummy = ActionEnvelope.build("__invalid__", "__invalid__", {})
            return Decision.deny(dummy.action_id, "Intent.action is required", reason_code="INVALID_INTENT")

        metadata = intent.get("metadata") or {}
        if not isinstance(metadata, dict):
            dummy = ActionEnvelope.build(str(action).strip(), "__invalid__", {})
            return Decision.deny(dummy.action_id, "Intent.metadata must be a mapping", reason_code="INVALID_INTENT")

        envelope = ActionEnvelope.build(
            action_type=action.strip(),
            resource=intent.get("resource", "__unspecified__"),
            parameters=metadata,
        )

        return self.evaluate(envelope)
