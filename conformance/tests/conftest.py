"""
conformance/tests/conftest.py

Shared fixtures and helpers for gate conformance tests.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
FIXTURES_DIR = REPO_ROOT / "conformance" / "fixtures"
DECISIONS_DIR = FIXTURES_DIR / "decisions"
SPEC_DIR = REPO_ROOT / "spec"


def load_fixture(rel_path: str) -> Dict[str, Any]:
    return json.loads((FIXTURES_DIR / rel_path).read_text())


def write_policy(content: str) -> str:
    """Write a temporary policy YAML and return its path."""
    f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml")
    f.write(content)
    f.close()
    return f.name


@pytest.fixture
def allow_policy_path():
    return write_policy(
        "rules:\n"
        "  - action: send_email\n"
        "    allowed: true\n"
        "  - action: read_file\n"
        "    allowed: true\n"
        "  - action: transfer_money\n"
        "    max_amount: 1000\n"
    )


@pytest.fixture
def deny_policy_path():
    return write_policy(
        "rules:\n"
        "  - action: dangerous_action\n"
        "    allowed: false\n"
    )
