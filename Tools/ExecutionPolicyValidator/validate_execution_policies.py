#!/usr/bin/env python3
"""Unity AI execution policyの最小整合性を外部Packageなしで検証します。"""

from __future__ import annotations

import sys
from pathlib import Path


REQUIRED_FILES = {
    "AGENTS.md": [
        "モード指定がない依頼は`prompt`",
        "`graph_loop`へ無断で切り替えない",
    ],
    "policies/execution-mode.yaml": [
        "default_mode: prompt",
        "silent_switch: false",
        "prompt_to_graph_loop_requires_confirmation: true",
    ],
    "policies/prompt-budget.yaml": [
        "max_parallel_workers: 1",
        "action: request_mode_decision",
    ],
    "policies/graph-loop-budget.yaml": [
        "max_parallel_nodes: 3",
        "require_budget_reservation: true",
    ],
    "policies/mode-escalation.yaml": [
        "score_threshold: 4",
        "required: true",
        "ask_once_per_goal: true",
    ],
    "schemas/execution-state.schema.yaml": [
        "execution_mode:",
        "mode_locked_for_goal:",
        "budget:",
    ],
    "schemas/evidence.schema.yaml": [
        "verdict:",
        "captured_at:",
    ],
    "skills/unity-execution-router/SKILL.md": [
        "無指定時は必ず`prompt`",
        "Graph / Loopへ自動変更しません",
    ],
    "skills/unity-prompt-execution/SKILL.md": [
        "Task Graphを展開せず",
        "Budget超過",
    ],
    "skills/unity-graph-engineering/SKILL.md": [
        "明示指定またはユーザー承認",
        "LoopはNode内部",
    ],
    "Tests/ExecutionRouting/cases.yaml": [
        "expected_initial_mode: prompt",
        "silent_switch_forbidden: true",
    ],
}


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    for relative_path, required_fragments in REQUIRED_FILES.items():
        path = root / relative_path
        if not path.is_file():
            errors.append(f"Missing file: {relative_path}")
            continue

        text = path.read_text(encoding="utf-8")
        for fragment in required_fragments:
            if fragment not in text:
                errors.append(f"Missing contract in {relative_path}: {fragment}")

    execution_mode = root / "policies/execution-mode.yaml"
    if execution_mode.is_file():
        text = execution_mode.read_text(encoding="utf-8")
        if "unspecified_request: prompt" not in text:
            errors.append("Unspecified requests must route to prompt.")
        if "explicit_selection_only: true" not in text:
            errors.append("Auto mode must remain explicit-selection only.")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    errors = validate(root)

    if errors:
        print("Execution policy validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Execution policy validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
