#!/usr/bin/env python3
"""Validate UnityAgent Handoff v2 and project it into execution-owned state fields."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "2.0"
PROFILES = {"generic_planning", "personal_full_control", "team_safe_import"}
CONTEXT_BUDGET_STATUSES = {"within_budget", "compression_required", "blocked", "unmeasured"}


class CompatibilityError(ValueError):
    """UnityAgent compatibility contract violation."""


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CompatibilityError(f"{label} must be a mapping")
    return value


def validate_handoff(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = (
        "schema_version",
        "task_id",
        "context_manifest_id",
        "context_manifest_schema_version",
        "route_id",
        "task_fingerprint",
        "task_contract_ref",
        "execution_profile",
        "risk_level",
        "selected_contexts",
        "context_budget_decision",
        "allowed_mutations",
        "prohibited_mutations",
        "required_quality_gates",
        "conditional_quality_gates",
        "unresolved_bindings",
    )
    errors.extend(f"missing required field: {field}" for field in required if field not in document)

    if document.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if document.get("execution_profile") not in PROFILES:
        errors.append("execution_profile is not supported")

    fingerprint = document.get("task_fingerprint")
    if isinstance(fingerprint, dict):
        required_fingerprint = {
            "intent",
            "artifact",
            "scope",
            "failure_mode",
            "architecture_state",
            "mutation_target",
            "evidence_state",
            "project_access",
        }
        missing = sorted(required_fingerprint - set(fingerprint))
        if missing:
            errors.append(f"task_fingerprint missing fields: {missing}")
    elif "task_fingerprint" in document:
        errors.append("task_fingerprint must be a mapping")

    context_budget = document.get("context_budget_decision")
    if isinstance(context_budget, dict):
        decision = context_budget.get("decision")
        if decision not in CONTEXT_BUDGET_STATUSES:
            errors.append("context_budget_decision.decision is invalid")
        if document.get("allowed_mutations") and decision != "within_budget":
            errors.append("mutation requires UnityAgent context budget within_budget")
    elif "context_budget_decision" in document:
        errors.append("context_budget_decision must be a mapping")

    if document.get("risk_level") == "R0" and document.get("allowed_mutations"):
        errors.append("R0 handoff cannot allow mutation")
    return errors


def build_state_patch(document: dict[str, Any]) -> dict[str, Any]:
    errors = validate_handoff(document)
    if errors:
        raise CompatibilityError("; ".join(errors))

    context_budget = _require_mapping(document["context_budget_decision"], "context_budget_decision")
    return {
        "execution_profile": document["execution_profile"],
        "domain_route": document["route_id"],
        "task_contract_id": Path(str(document["task_contract_ref"])).stem,
        "unityagent_handoff": {
            "schema_version": document["schema_version"],
            "task_id": document["task_id"],
            "context_manifest_id": document["context_manifest_id"],
            "context_manifest_schema_version": document["context_manifest_schema_version"],
            "task_fingerprint": document["task_fingerprint"],
            "task_contract_ref": document["task_contract_ref"],
            "risk_level": document["risk_level"],
            "selected_contexts": document["selected_contexts"],
            "context_budget_decision": context_budget,
            "allowed_mutations": document["allowed_mutations"],
            "prohibited_mutations": document["prohibited_mutations"],
            "required_quality_gates": document["required_quality_gates"],
            "conditional_quality_gates": document["conditional_quality_gates"],
            "unresolved_bindings": document["unresolved_bindings"],
        },
        "mutation_allowed_by_context_budget": context_budget.get("decision") == "within_budget",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        document = json.loads(args.handoff.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise CompatibilityError("handoff root must be a mapping")
        patch = build_state_patch(document)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(patch, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, CompatibilityError) as exc:
        print(f"UnityAgent handoff v2 rejected: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
