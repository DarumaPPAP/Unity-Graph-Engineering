#!/usr/bin/env python3
"""Unity AI execution policyの最小整合性を外部Packageなしで検証します。"""

from __future__ import annotations

import sys
from pathlib import Path


REQUIRED_FILES = {
    "AGENTS.md": [
        "モード指定がない依頼は`prompt`",
        "`graph_loop`へ無断で切り替えない",
        "IxはOptional Code Intelligence",
        "QuotaはPermissionではない",
        "User Policyへ自動昇格しない",
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
    "policies/external-providers.yaml": [
        "auto_install: false",
        "probe_external_providers: false",
        "direct_source_read_required_before_mutation: true",
    ],
    "policies/continuation-control.yaml": [
        "quota_is_permission: false",
        "continuation_requires_valid_writeback: true",
        "unbounded_autonomy_forbidden: true",
    ],
    "policies/memory-layering.yaml": [
        "raw_evidence_required: true",
        "symbolic_projection_is_not_source_of_truth: true",
        "auto_update_user_policy: false",
    ],
    "schemas/execution-state.schema.yaml": [
        "execution_mode:",
        "mode_locked_for_goal:",
        "continuation:",
        "memory_projection:",
        "budget:",
    ],
    "schemas/evidence.schema.yaml": [
        "verdict:",
        "captured_at:",
    ],
    "schemas/continuation-state.schema.yaml": [
        "decision:",
        "compute_share:",
        "writeback_complete:",
    ],
    "schemas/memory-layer.schema.yaml": [
        "L0_raw_evidence",
        "L3_reusable_candidate",
        "promotion_target:",
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
        "IxはNavigation Layer",
        "QuotaはPermissionでもBudgetでもありません",
        "L0 Raw Evidence",
    ],
    "Tests/ExecutionRouting/cases.yaml": [
        "expected_initial_mode: prompt",
        "silent_switch_forbidden: true",
    ],
    "Tests/ExternalProviders/cases.yaml": [
        "ix-unavailable-does-not-block",
        "quota-cannot-bypass-human-gate",
        "user-policy-promotion-needs-human",
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

    external_providers = root / "policies/external-providers.yaml"
    if external_providers.is_file():
        text = external_providers.read_text(encoding="utf-8")
        if "team_safe_import:" not in text or "probe_external_providers: false" not in text:
            errors.append("Team Safe Import must not probe external providers.")
        if "auto_install: false" not in text:
            errors.append("External providers must not auto-install.")

    continuation = root / "policies/continuation-control.yaml"
    if continuation.is_file():
        text = continuation.read_text(encoding="utf-8")
        if "quota_is_permission: false" not in text:
            errors.append("Quota must remain separate from permission.")

    memory = root / "policies/memory-layering.yaml"
    if memory.is_file():
        text = memory.read_text(encoding="utf-8")
        if "raw_evidence_required: true" not in text:
            errors.append("Layered memory must preserve raw evidence.")
        if "auto_update_user_policy: false" not in text:
            errors.append("Memory must not auto-update user policy.")

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
