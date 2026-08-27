#!/usr/bin/env python3
"""Validate local UnityAgent compatibility policy, schema, and adapters."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {
    "policies/unityagent-compatibility.yaml": [
        'schema_version: "1.0"',
        'schema_version: "2.0"',
        "recompute_in_execution_owner: false",
        "mutation_requires: within_budget",
        "unavailable_is_not_automatic_graph_escalation: true",
        "Tools/BehaviorEvalAdapter/behavior_eval_adapter.py",
    ],
    "policies/contract-routing.yaml": [
        "task_fingerprint_is_owned_by_UnityAgent: true",
        "execution_owner_must_not_rederive_primary_route_when_handoff_v2_is_valid: true",
        "context_manifest_id_must_be_preserved_across_handoff: true",
        "required_and_conditional_quality_gates_must_remain_distinct: true",
    ],
    "policies/prompt-budget.yaml": [
        "consume_unityagent_context_budget_decision: true",
        "do_not_recompute_unityagent_context_budget: true",
        "unavailable_alone_triggers_graph_escalation: false",
    ],
    "schemas/unityagent-handoff-v2.schema.yaml": [
        'const: "2.0"',
        "context_manifest_id",
        "task_fingerprint",
        "context_budget_decision",
        "const: within_budget",
    ],
    "schemas/execution-state.schema.yaml": [
        "unityagent_handoff:",
        'schema_version: {const: "2.0"}',
        "context_budget_decision:",
        "required_quality_gates:",
        "conditional_quality_gates:",
    ],
    "Tools/UnityAgentCompatibility/handoff_adapter.py": [
        'SCHEMA_VERSION = "2.0"',
        "mutation requires UnityAgent context budget within_budget",
        "unityagent_handoff",
    ],
    "Tools/BehaviorEvalAdapter/behavior_eval_adapter.py": [
        'MODE_MAP = {"prompt": "prompt", "graph_loop": "graph_loop"}',
        '"implementation": "mutation"',
        "shell=False",
        "UNITYAGENT_PRODUCTION_COMMAND_JSON",
        "execution-envelope.yaml",
    ],
}


def main() -> int:
    errors: list[str] = []
    for relative, fragments in REQUIRED.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"Missing compatibility file: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment not in text:
                errors.append(f"Missing compatibility contract in {relative}: {fragment}")

    adapter = (ROOT / "Tools/BehaviorEvalAdapter/behavior_eval_adapter.py").read_text(encoding="utf-8")
    if '"graph": "graph_loop"' in adapter:
        errors.append("Behavior adapter must not silently accept legacy graph alias.")
    if "shell=True" in adapter:
        errors.append("Behavior adapter must never use shell=True.")

    if errors:
        print("Local UnityAgent compatibility validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Local UnityAgent compatibility validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
