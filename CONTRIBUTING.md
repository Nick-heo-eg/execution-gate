# Contributing Guidelines

Before submitting a PR, answer these questions:

1. **Which layer does this belong to?** See [LAYER_REGISTRY.md](https://github.com/Nick-heo-eg/execution-boundary/blob/master/LAYER_REGISTRY.md).
2. **Does an existing repository already own this responsibility?** If yes, the PR goes there.
3. **Is this a `core-spec` change?** Core changes require an RFC. See below.
4. **Is this a bug fix?** Reference an existing issue.
5. **Is this an architectural change?** Start in Discussions first.

PRs that do not follow the layer ownership model may be closed without review.

## Core Spec Changes (RFC Required)

`execution-boundary-core-spec` is frozen. Changes to Envelope, Decision, or Ledger schemas require an RFC.

Open an issue with the RFC template before writing code:
→ [RFC template](https://github.com/Nick-heo-eg/execution-boundary-core-spec/blob/main/docs/rfc-template.md)

## Bug Fixes

- Open an issue first
- Reference the issue in your PR
- Include a test that fails before the fix

## New Transport / Profile

- Update `LAYER_REGISTRY.md` in `execution-boundary` first
- The new repo must define what it is AND what it is not in the first paragraph of README
- Include at least one DENY case in the README
