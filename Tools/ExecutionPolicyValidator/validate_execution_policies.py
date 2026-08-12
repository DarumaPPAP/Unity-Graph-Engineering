#!/usr/bin/env python3
"""Validate Unity Graph Engineering execution/control-plane coherence."""

from __future__ import annotations

import sys
from pathlib import Path


REQUIRED = {
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
    "policies/prompt-budget.yaml": ["max_parallel_workers: 1", "action: request_mode_decision"],
    "policies/graph-loop-budget.yaml": ["max_parallel_nodes: 3", "require_budget_reservation: true"],
    "policies/mode-escalation.yaml": ["score_threshold: 4", "required: true", "ask_once_per_goal: true"],
    "policies/external-providers.yaml": [
        "auto_install: false",
        "probe_external_providers: false",
        "direct_source_read_required_before_mutation: true",
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
        "expired_lease_returns_todo_to_unclaimed: true",
    ],
    "policies/memory-layering.yaml": [
        "raw_evidence_required: true",
        "symbolic_projection_is_not_source_of_truth: true",
        "auto_update_user_policy: false",
        "controller_writes_external_authority: false",
        "scope_propagation_required: true",
        "scope_downgrade_forbidden: true",
        "non_personal_project_internal_read_forbidden: true",
        "legacy_record_without_scope: project_internal",
        "access_filter_before_ranking: true",
        "hard_max_items: 20",
        "hard_max_characters: 12000",
        "raw_content_requires_explicit_drilldown: true",
    ],
    "policies/execution-orchestration.yaml": [
        "implementation: Tools/ExecutionOrchestrator/execution_orchestrator.py",
        "graph_loop_only: true",
        "orchestrator_owns_source_mutation: false",
        "orchestrator_owns_state_current: false",
        "orchestrator_owns_human_gate: false",
        "orchestrator_owns_quota_policy: false",
        "arbitrary_command_passthrough: false",
        "child_process_shell: false",
        "multiple_worker_claim_requires_durable_writeback_before_work: true",
        "evidence_must_be_durable_before_quota_spend: true",
        "finalize_must_be_idempotent_after_quota_spent: true",
        "team_safe_ix_probe_forbidden: true",
        "generic_planning_ix_probe_forbidden: true",
        "non_personal_project_internal_memory_forbidden: true",
    ],
    "schemas/execution-state.schema.yaml": [
        "goal_id:", "health:", "human_gate:", "quota:", "worker:", "todos:",
        "previous_slice:", "quota_spent:", "orchestration:", "memory_projection:", "remaining:",
    ],
    "schemas/evidence.schema.yaml": ["verdict:", "captured_at:"],
    "schemas/continuation-state.schema.yaml": [
        "native_continuation", "should_run:", "budget_guard", "runnable_candidates:",
        "blocked_candidates:", "allowed_slots:",
    ],
    "schemas/memory-layer.schema.yaml": [
        "L0_raw_evidence", "L3_reusable_candidate", "sha256:", "execution_profile:",
        "scope_class:", "enum: [project_internal, portable_artifact, public_reference]",
        "additionalProperties: false",
    ],
    "schemas/execution-orchestration.schema.yaml": [
        "execution_orchestrator", "ticket_digest:", "quota_spent:", "orchestrated:",
        "owns_state_current:", "const: false",
    ],
    "skills/unity-execution-router/SKILL.md": ["無指定時は必ず`prompt`", "Graph / Loopへ自動変更しません"],
    "skills/unity-prompt-execution/SKILL.md": ["Task Graphを展開せず", "Budget超過"],
    "skills/unity-graph-engineering/SKILL.md": [
        "明示指定またはユーザー承認", "LoopはNode内部", "IxはNavigation Layer", "L0 Raw Evidence",
    ],
    "Tools/IxAdapter/ix_adapter.py": [
        "SAFE_OPERATIONS", "DEFAULT_TRACE_DEPTH = 3", "DEFAULT_TRACE_CAP = 100",
        "shell=False", "fallback=\"targeted_source_read\"",
    ],
    "Tools/ContinuationController/continuation_controller.py": [
        "def evaluate(", "def claim(", "def spend(", "OWNER_HELD_CAPABILITIES",
        "monitor_quiet_skip", "quota cannot be spent before durable writeback",
    ],
    "Tools/LayeredMemoryController/layered_memory_controller.py": [
        "def capture_raw(", "def create_atom(", "def create_scenario(", "def create_candidate(",
        "def retrieve(", "def drilldown(", "def project(", "def promote(",
        "SAFE_SCOPES", "SCOPE_RANK", "scope_downgrade_forbidden", "memory_scope_filtered",
        "def _read_request(", "MAX_ITEMS = 20", "MAX_CHARS = 12000", "writes_external_authority",
    ],
    "Tools/ExecutionOrchestrator/execution_orchestrator.py": [
        "def prepare(", "def finalize(", "shell=False", "controller_identity_mismatch",
        "ticket_integrity_failed", "write_claim_to_authoritative_state",
        "evidence_preserved_without_quota_spend", "finalize_idempotent_replay",
        "owns_state_current", "memory_scope_leak", "direct_source_read",
    ],
    "Tests/ExecutionRouting/cases.yaml": ["expected_initial_mode: prompt", "silent_switch_forbidden: true"],
    "Tests/ExternalProviders/cases.yaml": [
        "ix-unavailable-does-not-block", "quota-cannot-bypass-human-gate",
        "user-policy-promotion-needs-human",
    ],
    "Tests/ExternalProviders/test_ix_adapter.py": [
        "test_missing_cli_is_unavailable_and_falls_back", "test_trace_is_bounded",
        "test_target_cannot_be_option_injection", "test_subprocess_never_uses_shell",
    ],
    "Tests/ExternalProviders/test_continuation_controller.py": [
        "test_human_gate_precedes_quota", "test_monitor_only_lane_is_quiet",
        "test_spend_updates_projection_only_after_validated_writeback",
    ],
    "Tests/ExternalProviders/test_layered_memory_controller.py": [
        "test_team_safe_scope_blocks_before_source_file_access", "test_scope_is_inherited_across_layers",
        "test_scope_downgrade_is_blocked", "test_team_safe_retrieve_filters_project_internal_memory",
        "test_legacy_record_without_scope_is_treated_as_internal",
        "test_team_safe_drilldown_cannot_open_internal_memory", "test_promotion_never_writes_unityagent",
    ],
    "Tests/ExternalProviders/test_execution_orchestrator.py": [
        "test_human_gate_short_circuits_before_other_controllers",
        "test_multiple_worker_requires_durable_claim_before_navigation",
        "test_team_safe_never_invokes_ix", "test_memory_raw_content_contract_breach_blocks",
        "test_ticket_tampering_is_detected", "test_finalize_orders_evidence_before_quota_spend",
        "test_memory_capture_failure_prevents_spend", "test_finalize_is_idempotent_after_quota_spent",
        "test_controller_subprocess_never_uses_shell",
    ],
}


def _ordered(text: str, first: str, second: str) -> bool:
    a, b = text.find(first), text.find(second)
    return a >= 0 and b >= 0 and a < b


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    for relative, fragments in REQUIRED.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"Missing file: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment not in text:
                errors.append(f"Missing contract in {relative}: {fragment}")

    mode = (root / "policies/execution-mode.yaml").read_text(encoding="utf-8")
    if "unspecified_request: prompt" not in mode:
        errors.append("Unspecified requests must route to prompt.")
    if "explicit_selection_only: true" not in mode:
        errors.append("Auto mode must remain explicit-selection only.")

    ix = (root / "Tools/IxAdapter/ix_adapter.py").read_text(encoding="utf-8")
    if '"reset",' in ix or "'reset'," in ix:
        errors.append("Ix reset must not appear in SAFE_OPERATIONS.")
    if "shell=False" not in ix or "shell=True" in ix:
        errors.append("Ix adapter must keep shell=False.")

    continuation = (root / "Tools/ContinuationController/continuation_controller.py").read_text(encoding="utf-8")
    if 'execution_mode != "graph_loop"' not in continuation:
        errors.append("Continuation controller must reject non graph_loop mode.")
    if "writeback_complete" not in continuation or "evidence_refs" not in continuation:
        errors.append("Continuation spend must remain tied to writeback and evidence.")

    memory = (root / "Tools/LayeredMemoryController/layered_memory_controller.py").read_text(encoding="utf-8")
    if not _ordered(memory, '_guard_scope(profile, scope, "capture")', "source = Path("):
        errors.append("Memory scope guard must execute before source-file access.")
    if not _ordered(memory, "if not _scope_allowed(profile, _record_scope(record)):", "score = _score(record, query, context)"):
        errors.append("Memory access scope must be filtered before retrieval ranking.")
    if '"writes_external_authority": False' not in memory:
        errors.append("Memory promotion must never write external authority directly.")
    if "legacy records without an explicit scope are treated as project-internal" not in memory.lower():
        errors.append("Legacy memory must fail closed to project_internal scope.")

    orchestrator = (root / "Tools/ExecutionOrchestrator/execution_orchestrator.py").read_text(encoding="utf-8")
    if "shell=False" not in orchestrator or "shell=True" in orchestrator or "os.system" in orchestrator:
        errors.append("Execution Orchestrator must use fixed shell=False subprocess contracts.")
    if not _ordered(orchestrator, 'decision = _continuation("evaluate"', "memory_projection = None"):
        errors.append("Continuation gate must run before memory navigation.")
    if not _ordered(orchestrator, 'decision = _continuation("evaluate"', "ix_result = None"):
        errors.append("Continuation gate must run before Ix navigation.")
    if not _ordered(orchestrator, "capture = _memory(workspace, capture_request)", 'spend = _continuation("spend"'):
        errors.append("Raw evidence must be captured before quota spend.")
    if "write_claim_to_authoritative_state" not in orchestrator:
        errors.append("Multiple-worker claims must require durable state writeback.")
    if "ticket_integrity_failed" not in orchestrator:
        errors.append("Execution ticket tamper detection is required.")
    if "finalize_idempotent_replay" not in orchestrator:
        errors.append("Finalize must prevent duplicate quota spend.")
    if '"owns_state_current": False' not in orchestrator:
        errors.append("Orchestrator must not own STATE/current.yaml authority.")

    execution_schema = (root / "schemas/execution-state.schema.yaml").read_text(encoding="utf-8")
    for field in ("goal_id:", "quota:", "worker:", "todos:", "previous_slice:", "quota_spent:"):
        if field not in execution_schema:
            errors.append(f"Execution state cannot represent control-plane field: {field}")

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
