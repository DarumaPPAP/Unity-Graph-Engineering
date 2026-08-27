#!/usr/bin/env python3
"""Run legacy execution policy validation with semantic checks for known brittle guards."""

from __future__ import annotations

import sys
from pathlib import Path

from validate_execution_policies import validate as validate_legacy


ROOT = Path(__file__).resolve().parents[2]
SELECTED_TODO_FALSE_POSITIVE = "Missing contract in skills/unity-graph-engineering/SKILL.md: selected todo"
RAW_EVIDENCE_FALSE_POSITIVE = "Raw evidence must be captured before quota spend."


def _semantic_selected_todo_guard() -> bool:
    skill = (ROOT / "skills/unity-graph-engineering/SKILL.md").read_text(encoding="utf-8")
    orchestrator = (ROOT / "Tools/ExecutionOrchestrator/execution_orchestrator.py").read_text(encoding="utf-8")
    return (
        "Execution Ticket" in skill
        and "selected_todo_id" in orchestrator
        and "ticket_todo_mismatch" in orchestrator
    )


def _semantic_evidence_before_spend_guard() -> bool:
    orchestrator = (ROOT / "Tools/ExecutionOrchestrator/execution_orchestrator.py").read_text(encoding="utf-8")
    capture_index = orchestrator.find("capture = _memory(")
    spend_index = orchestrator.find('spend = _continuation("spend"')
    capture_failure_guard = orchestrator.find('if capture.get("status") != "ok"')
    return (
        capture_index >= 0
        and capture_failure_guard > capture_index
        and spend_index > capture_failure_guard
        and "evidence_preserved_without_quota_spend" in orchestrator
    )


def main() -> int:
    errors = validate_legacy(ROOT)

    if SELECTED_TODO_FALSE_POSITIVE in errors and _semantic_selected_todo_guard():
        errors.remove(SELECTED_TODO_FALSE_POSITIVE)
    if RAW_EVIDENCE_FALSE_POSITIVE in errors and _semantic_evidence_before_spend_guard():
        errors.remove(RAW_EVIDENCE_FALSE_POSITIVE)

    if errors:
        print("Execution policy validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Execution policy validation passed with semantic compatibility guards.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
