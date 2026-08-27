#!/usr/bin/env python3
"""Validate the local execution boundary against a checked-out UnityAgent revision."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


EXPECTED_HANDOFF = "2.0"
EXPECTED_MANIFEST = "3.1"


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping: {path}")
    return data


def validate(unityagent_root: Path) -> list[str]:
    errors: list[str] = []
    required_paths = {
        "handoff": unityagent_root / "Tools" / "LoopIntegration" / "handoff.py",
        "manifest": unityagent_root / ".ai" / "context-manifest.schema.yaml",
        "context_budget": unityagent_root / ".ai" / "context-budget.yaml",
        "behavior_contract": unityagent_root / ".ai" / "eval" / "behavior-eval-contract.yaml",
        "behavior_request": unityagent_root / "Tests" / "BehaviorEval" / "behavior-eval-request.schema.yaml",
        "behavior_envelope": unityagent_root / "Tests" / "BehaviorEval" / "execution-envelope.schema.yaml",
    }
    for label, path in required_paths.items():
        if not path.is_file():
            errors.append(f"UnityAgent required contract missing: {label}: {path}")
    if errors:
        return errors

    handoff_text = required_paths["handoff"].read_text(encoding="utf-8")
    match = re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)["\']', handoff_text, re.MULTILINE)
    if not match or match.group(1) != EXPECTED_HANDOFF:
        errors.append(f"UnityAgent handoff schema must be {EXPECTED_HANDOFF}")
    for field in (
        "context_manifest_id",
        "context_manifest_schema_version",
        "task_fingerprint",
        "task_contract_ref",
        "context_budget_decision",
        "required_quality_gates",
        "conditional_quality_gates",
    ):
        if field not in handoff_text:
            errors.append(f"UnityAgent Handoff v2 missing compatibility field: {field}")

    manifest = _load_yaml(required_paths["manifest"])
    if str(manifest.get("schema_version")) != EXPECTED_MANIFEST:
        errors.append(f"UnityAgent Context Manifest must be {EXPECTED_MANIFEST}")
    budget = manifest.get("budget", {}) or {}
    decision = budget.get("decision", {}) or {}
    allowed = set(decision.get("allowed", []) or []) if isinstance(decision, dict) else set()
    required_decisions = {"within_budget", "compression_required", "blocked", "unmeasured"}
    if not required_decisions.issubset(allowed):
        errors.append("UnityAgent Context Manifest budget decisions drifted from execution compatibility contract")

    context_budget = _load_yaml(required_paths["context_budget"])
    guards = context_budget.get("execution_guards", {}) or {}
    if guards.get("mutation_requires_within_budget") is not True:
        errors.append("UnityAgent Context Budget no longer requires within_budget before mutation")

    behavior_contract = _load_yaml(required_paths["behavior_contract"])
    ownership = behavior_contract.get("ownership", {}) or {}
    if ownership.get("execution_runtime") != "DarumaPPAP/Unity-Graph-Engineering":
        errors.append("UnityAgent Behavior Eval execution ownership changed")
    rules = behavior_contract.get("rules", {}) or {}
    if rules.get("production_execution_path_required") is not True:
        errors.append("UnityAgent Behavior Eval no longer requires production execution path")
    if rules.get("one_agent_attempt_for_smoke") is not True:
        errors.append("UnityAgent Behavior Eval smoke attempt contract changed")

    behavior_request = _load_yaml(required_paths["behavior_request"])
    mode = ((behavior_request.get("execution_fields", {}) or {}).get("mode", {}) or {})
    allowed_modes = set(mode.get("allowed", []) or [])
    if allowed_modes != {"prompt", "graph_loop"}:
        errors.append(f"UnityAgent Behavior Eval mode vocabulary drifted: {sorted(allowed_modes)}")

    envelope = _load_yaml(required_paths["behavior_envelope"])
    rules = envelope.get("rules", {}) or {}
    if rules.get("execution_owner_repository_must_be_DarumaPPAP_Unity_Graph_Engineering") is not True:
        errors.append("UnityAgent execution envelope ownership rule changed")
    if rules.get("smoke_agent_attempt_must_equal_one") is not True:
        errors.append("UnityAgent execution envelope smoke attempt rule changed")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unityagent-root", type=Path, required=True)
    args = parser.parse_args()
    errors = validate(args.unityagent_root.resolve())
    if errors:
        print("UnityAgent compatibility validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("UnityAgent compatibility validation passed: Handoff v2 / Context Manifest v3.1 / Behavior Eval v1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
