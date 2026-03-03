# Changelog

All notable changes to `execution-gate` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [Unreleased]

---

## [0.3.0] - 2026-03-04

### Added
- `gate/telemetry.py` — optional OTel integration (no-op without `opentelemetry-api`)
- `Gate.evaluate()` emits `eb.evaluate` OTel span with `eb.*` semantic conventions
- `eb.envelope_id`, `eb.decision`, `eb.reason_code`, `eb.ledger_commit`, `eb.proof_hash` attributes per observability pattern spec
- `_evaluate_inner()` extracted — pure evaluation logic separated from observability concerns
- `[otel]` optional dependency group: `opentelemetry-api/sdk/exporter-otlp-proto-grpc>=1.24.0`
- `eb.ledger.append` span context manager in telemetry module

### Changed
- `pyproject.toml` version bumped to `0.3.0`

### Notes
- OTel is fully optional. Gate behavior is identical with or without `opentelemetry-api` installed.
- Standard OTel env vars apply: `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`
- Install: `pip install execution-gate[otel]`

---

## [0.2.0] - 2026-03-03

### Added
- Core Spec alignment: `ActionEnvelope` dataclass with `build()` factory
- `Decision` now includes `decision_id`, `authority_token`, `proof_hash` (SHA-256)
- `DENY` replaces `BLOCK` — conforms to Core Spec state model
- Pinned `spec/action-envelope.schema.json` and `spec/decision.schema.json` from core-spec commit `47588ff`
- `SECURITY.md` — private vulnerability disclosure via GitHub Advisories

---

## [0.1.0] - 2026-02-20

### Added
- Initial release: `Gate`, `enforce()` decorator, `BlockedByGate` exception
- Fail-closed: evaluator failure → DENY
- YAML policy with `max_amount` and `allowed` rules
- `emit_audit()` — structured JSON audit log (ALLOW and DENY)
- `gate-demo` CLI entry point

