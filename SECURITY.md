# Security Policy

If you discover a security vulnerability, please **do not open a public issue**.

Report privately via GitHub: [Security Advisories](../../security/advisories/new)

We aim to acknowledge reports within 72 hours.

Please include:
- Description of the vulnerability
- Reproduction steps
- Affected versions
- Impact assessment (if known)

We will coordinate disclosure after validation and patch.

## Scope

Security reports are applicable to:
- `execution-boundary-core-spec` — schema definitions
- `execution-gate` — policy evaluation logic
- `agent-execution-guard` — ED25519 signing, ledger integrity, enforcement path
- `execution-boundary-transport-profile` — Merkle ledger, canonical export
