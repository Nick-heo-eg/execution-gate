"""CLI demo for deterministic execution gate."""
from __future__ import annotations

import sys
from pathlib import Path

from .core import Firewall
from .logger import emit_audit


def demo():
    """Run a quick demonstration of the execution gate."""

    print("=" * 60)
    print("Deterministic Execution Gate - Quick Demo")
    print("=" * 60)
    print()

    # Find policy.yaml (try current dir, then package dir)
    policy_path = Path("policy.yaml")
    if not policy_path.exists():
        package_dir = Path(__file__).parent.parent
        policy_path = package_dir / "policy.yaml"

    if not policy_path.exists():
        print("❌ Error: policy.yaml not found")
        print("   Run this command from the repository root, or:")
        print("   python -m examples.local_agent_demo")
        sys.exit(1)

    fw = Firewall(
        policy_path=str(policy_path),
        platform="demo-cli",
        model="example",
        audit_file=None,  # stdout
    )

    test_cases = [
        {
            "name": "✅ Small transfer (allowed)",
            "intent": {"actor": "agent", "action": "transfer_money", "metadata": {"amount": 500}},
        },
        {
            "name": "❌ Large transfer (blocked - exceeds limit)",
            "intent": {"actor": "agent", "action": "transfer_money", "metadata": {"amount": 5000}},
        },
        {
            "name": "❌ Delete database (blocked - explicitly denied)",
            "intent": {"actor": "agent", "action": "delete_database", "metadata": {}},
        },
        {
            "name": "❌ Unknown action (blocked - no rule)",
            "intent": {"actor": "agent", "action": "unknown_action", "metadata": {}},
        },
    ]

    for idx, case in enumerate(test_cases, 1):
        print(f"{idx}. {case['name']}")
        decision = fw.check(case["intent"])

        emit_audit(
            intent=case["intent"],
            decision=decision,
            platform=fw.platform,
            model=fw.model,
            out_file=fw.audit_file,
        )

        print(f"   Decision: {decision.status}")
        if decision.reason:
            print(f"   Reason: {decision.reason}")
        print()

    print("=" * 60)
    print("All audit logs above show structured JSON format.")
    print("Fail-closed by default: unknown/missing policy → BLOCK")
    print("=" * 60)


def main():
    """Entry point for CLI."""
    demo()


if __name__ == "__main__":
    main()
