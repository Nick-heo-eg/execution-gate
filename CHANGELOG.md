# Changelog

All notable changes to `execution-gate` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [Unreleased]

---

## [0.2.0] - 2026-03-03

### Added
- Core Spec alignment: `ActionEnvelope` dataclass with `build()` factory
- `Decision` now includes `decision_id`, `authority_token`, `proof_hash` (SHA-256)
- `DENY` replaces `BLOCK` — conforms to Core Spec state model
- Pinned `spec/action-envelope.schema.json` and `spec/decision.schema.json` from core-spec commit `47588ff`
- `SECURITY.md` — private vulnerability disclosure via GitHub Advisories
- `CONTRIBUTING.md` — layer ownership gate before PR

### Changed
- `evaluate(envelope)` replaces `check()` as primary interface (`check()` retained as compatibility wrapper)
- `Ledger` now records structured `envelope + decision` entries
- README aligned to Core Spec conformance table

### Internal
- `proof_hash` computed as `SHA-256(decision_id + action_id + result + timestamp)`
- All decisions — ALLOW and DENY — appended to ledger unconditionally

---

## [0.1.0] - 2026-02-22

### Added
- `Gate` class: deterministic fail-closed evaluation
- YAML policy engine: `max_amount`, `blocked_actions`, `require_confirmation`
- `ActionEnvelope` proposal object
- `BlockedByGate` exception on DENY
- CLI demo: `gate-demo`
- Example: `examples/simple_agent.py` — before/after boundary pattern

### Changed
- Renamed `Firewall` → `Gate` throughout (`BlockedByFirewall` → `BlockedByGate`)
- README reframed: problem-solution structure, concrete behavior first
