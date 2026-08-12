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
        "path: Tools/IxAdapter/ix_adapter.py",
        "arbitrary_command_passthrough: false",
        "destructive_commands_exposed: false",
        "trace_must_be_bounded: true",
        "reset_command_forbidden: true",
    ],
    "policies/continuation-control.yaml": [
        "quota_is_permission: false",
        "continuation_requires_valid_writeback: true",
        "unbounded_autonomy_forbidden: true",
        "implementation: Tools/ContinuationController/continuation_controller.py",
        "quota_spend_requires_validated_writeback: true",
        "continuous_monitor:",
        "expired_lease_returns_todo_to_unclaimed: true",
    ],
    "policies/memory-layering.yaml": [
        "raw_evidence_required: true",
        "symbolic_projection_is_not_source_of_truth: true",
        "auto_update_user_policy: false",
        "implementation: Tools/LayeredMemoryController/layered_memory_controller.py",
        "controller_writes_external_authority: false",
        "team_safe_scope_guard_before_source_read: true",
        "hard_max_items: 20",
        "hard_max_characters: 12000",
        "raw_content_requires_explicit_drilldown: true",
    ],
    "schemas/execution-state.schema.yaml": [
        "execution_mode:",
        "mode_locked_for_goal:",
        "continuation:",
        "should_run:",
        "budget_guard",
        "memory_projection:",
        "budget:",
    ],
    "schemas/evidence.schema.yaml": [
        "verdict:",
        "captured_at:",
    ],
    "schemas/continuation-state.schema.yaml": [
        "native_continuation",
        "should_run:",
        "budget_guard",
        "runnable_candidates:",
        "blocked_candidates:",
        "allowed_slots:",
    ],
    "schemas/memory-layer.schema.yaml": [
        "L0_raw_evidence",
        "L3_reusable_candidate",
        "sha256:",
        "execution_profile:",
        "scope_class:",
        "promotion_target:",
        "additionalProperties: false",
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
        "Tools/ContinuationController/continuation_controller.py",
        "WritebackとEvidenceなしではQuotaをSpendせず",
        "L0 Raw Evidence",
    ],
    "skills/unity-graph-engineering/references/code-intelligence-provider.md": [
        "Tools/IxAdapter/ix_adapter.py",
        "shell=False",
        "--depth 3 --cap 100",
        "targeted_source_read",
    ],
    "skills/unity-graph-engineering/references/continuation-control.md": [
        "Native LoopX-inspired Controller",
        "evaluate",
        "claim",
        "spend",
        "monitor_quiet_skip",
    ],
    "skills/unity-graph-engineering/references/layered-memory.md": [
        "Tools/LayeredMemoryController/layered_memory_controller.py",
        "source file read前",
        "Raw content: default OFF",
        "promote`は**Projectionを返すだけ**",
    ],
    "Tools/IxAdapter/ix_adapter.py": [
        "SAFE_OPERATIONS",
        "DEFAULT_TRACE_DEPTH = 3",
        "DEFAULT_TRACE_CAP = 100",
        "shell=False",
        "fallback=\"targeted_source_read\"",
    ],
    "Tools/ContinuationController/continuation_controller.py": [
        "def evaluate(",
        "def claim(",
        "def spend(",
        "OWNER_HELD_CAPABILITIES",
        "monitor_quiet_skip",
        "quota cannot be spent before durable writeback",
    ],
    "Tools/LayeredMemoryController/layered_memory_controller.py": [
        "def capture_raw(",
        "def create_atom(",
        "def create_scenario(",
        "def create_candidate(",
        "def retrieve(",
        "def drilldown(",
        "def project(",
        "def promote(",
        "TEAM_SAFE_SCOPES",
        "MAX_ITEMS = 20",
        "MAX_CHARS = 12000",
        "writes_external_authority",
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
    "Tests/ExternalProviders/test_ix_adapter.py": [
        "test_missing_cli_is_unavailable_and_falls_back",
        "test_trace_is_bounded",
        "test_target_cannot_be_option_injection",
        "test_subprocess_never_uses_shell",
    ],
    "Tests/ExternalProviders/test_continuation_controller.py": [
        "test_human_gate_precedes_quota",
        "test_monitor_only_lane_is_quiet",
        "test_spend_updates_projection_only_after_validated_writeback",
    ],
    "Tests/ExternalProviders/test_layered_memory_controller.py": [
        "test_capture_preserves_raw_and_sha256",
        "test_team_safe_scope_blocks_before_source_file_access",
        "test_retrieve_prefers_higher_layer_and_never_includes_raw_content",
        "test_user_policy_candidate_requires_human_gate",
        "test_promotion_never_writes_unityagent",
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
        if "arbitrary_command_passthrough: false" not in text:
            errors.append("Ix adapter must not expose arbitrary command passthrough.")
        if "destructive_commands_exposed: false" not in text:
            errors.append("Ix adapter must not expose destructive commands.")

    ix_adapter = root / "Tools/IxAdapter/ix_adapter.py"
    if ix_adapter.is_file():
        text = ix_adapter.read_text(encoding="utf-8")
        if '"reset",' in text or "'reset'," in text:
            errors.append("Ix reset must not appear in SAFE_OPERATIONS.")
        if "shell=False" not in text:
            errors.append("Ix adapter subprocess execution must keep shell=False.")
        if "DEFAULT_TRACE_DEPTH = 3" not in text or "DEFAULT_TRACE_CAP = 100" not in text:
            errors.append("Ix trace must keep bounded defaults.")

    continuation = root / "policies/continuation-control.yaml"
    if continuation.is_file():
        text = continuation.read_text(encoding="utf-8")
        if "quota_is_permission: false" not in text:
            errors.append("Quota must remain separate from permission.")
        if "quota_spend_requires_validated_writeback: true" not in text:
            errors.append("Quota spend must require validated writeback.")
        if "controller_does_not_own_state_authority: true" not in text:
            errors.append("Continuation controller must remain a projection, not state authority.")

    continuation_controller = root / "Tools/ContinuationController/continuation_controller.py"
    if continuation_controller.is_file():
        text = continuation_controller.read_text(encoding="utf-8")
        if "execution_mode != \"graph_loop\"" not in text:
            errors.append("Continuation controller must reject non graph_loop execution mode.")
        if "writeback_complete" not in text or "evidence_refs" not in text:
            errors.append("Continuation quota spend must remain tied to writeback and evidence.")
        if "OWNER_HELD_CAPABILITIES" not in text:
            errors.append("Continuation controller must preserve owner-held capability routing.")

    memory = root / "policies/memory-layering.yaml"
    if memory.is_file():
        text = memory.read_text(encoding="utf-8")
        if "raw_evidence_required: true" not in text:
            errors.append("Layered memory must preserve raw evidence.")
        if "auto_update_user_policy: false" not in text:
            errors.append("Memory must not auto-update user policy.")
        if "controller_writes_external_authority: false" not in text:
            errors.append("Memory controller must not own UnityAgent or user-policy authority.")
        if "raw_content_requires_explicit_drilldown: true" not in text:
            errors.append("Raw memory content must require explicit drill-down.")

    memory_controller = root / "Tools/LayeredMemoryController/layered_memory_controller.py"
    if memory_controller.is_file():
        text = memory_controller.read_text(encoding="utf-8")
        guard = text.find("profile, scope = _guard_capture_scope(request)")
        source_read = text.find("raw = source.read_bytes()")
        if guard < 0 or source_read < 0 or guard > source_read:
            errors.append("Team Safe memory scope guard must execute before reading the source file.")
        if '"writes_external_authority": False' not in text:
            errors.append("Memory promotion must remain a projection and never write external authority directly.")
        if '"raw_content_included": False' not in text:
            errors.append("Memory retrieval/projection must exclude raw content by default.")
        if "MAX_ITEMS = 20" not in text or "MAX_CHARS = 12000" not in text:
            errors.append("Memory retrieval must keep hard item and character bounds.")
        if "secret_capture_forbidden" not in text:
            errors.append("Memory capture must keep the secret-capture guard.")

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
