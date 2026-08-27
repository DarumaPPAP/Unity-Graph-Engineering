#!/usr/bin/env python3
"""Phase 1.1 Behavior Eval Adapter with runtime failure taxonomy and preserved evidence."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

import behavior_eval_adapter as legacy

CODEX_RUNTIME_DIR = Path(__file__).resolve().parents[1] / "CodexProductionAgent"
if str(CODEX_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(CODEX_RUNTIME_DIR))
from process_runtime import run_streaming_process, utf8_child_env  # noqa: E402

INFRASTRUCTURE_FAILURES = {
    "evaluator_contract_failure",
    "runtime_timeout",
    "runtime_protocol_failure",
    "unavailable_required_evidence",
    "task_fixture_invalid",
}
EXTRA_EVIDENCE = ("codex-events.jsonl", "codex-stderr.txt")


def _ensure_failure_bundle(staging: Path, request: dict[str, Any], message: str, failure_class: str) -> None:
    staging.mkdir(parents=True, exist_ok=True)
    task_id = str(request.get("golden_task_id") or "")
    if not (staging / "context-manifest.yaml").is_file():
        manifest = {
            "schema_version": "3.1",
            "id": f"{task_id or 'unknown'}-adapter-failure",
            "attempt": 1,
            "task": {
                "id": task_id,
                "route": "",
                "fingerprint": {
                    "intent": "unknown", "artifact": "unknown", "scope": "unknown",
                    "failure_mode": "unknown", "architecture_state": "unknown",
                    "mutation_target": "unknown", "evidence_state": "unknown", "project_access": "unknown",
                },
            },
            "policy": {"loaded": []},
            "knowledge": {"loaded": []},
            "harness": {"quality_gates": []},
            "execution": {
                "evidence": [], "unresolved_bindings": [message], "status": "failed",
                "failure_class": failure_class,
            },
        }
        (staging / "context-manifest.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    if not (staging / "response.md").is_file():
        (staging / "response.md").write_text(message.rstrip() + "\n", encoding="utf-8")
    if not (staging / "artifact-index.yaml").is_file():
        (staging / "artifact-index.yaml").write_text(
            yaml.safe_dump({"schema_version": "1.0", "artifacts": []}, sort_keys=False), encoding="utf-8"
        )
    metadata_path = staging / "execution-metadata.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata.setdefault("status", "unavailable" if failure_class == "runtime_timeout" else "failed")
    metadata.setdefault("execution_class", "production")
    metadata.setdefault("agent_id", "production-agent")
    metadata.setdefault("provider", "unavailable")
    metadata.setdefault("model", "unavailable")
    metadata.setdefault("model_revision", "unavailable")
    metadata["failure_class"] = failure_class
    metadata.setdefault("infrastructure_attempts", 1)
    metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _copy_bundle(staging: Path, publish: Path) -> None:
    legacy._copy_evidence(staging, publish)
    for name in EXTRA_EVIDENCE:
        source = staging / name
        if source.is_file():
            shutil.copy2(source, publish / name)


def _write_envelope_v2(
    request: dict[str, Any], publish: Path, *, command: list[str], fixture_hash: str,
    mode: str, metadata: dict[str, Any], process_returncode: int, adapter_runtime: dict[str, Any],
) -> None:
    revision = legacy._git_revision(legacy.ROOT)
    provider = str(metadata.get("provider") or "unavailable")
    model = str(metadata.get("model") or "unavailable")
    model_revision = str(metadata.get("model_revision") or "unavailable")
    failure_class = str(metadata.get("failure_class") or "").strip()
    if process_returncode != 0 and not failure_class:
        failure_class = "runtime_protocol_failure"
    observation_state = "not_observed" if failure_class in INFRASTRUCTURE_FAILURES else "observed"
    status = legacy._resolved_status(metadata, process_returncode)
    if failure_class == "runtime_timeout":
        status = "unavailable"

    evidence: dict[str, Any] = {
        "context_manifest": "context-manifest.yaml",
        "response": "response.md",
        "artifact_index": "artifact-index.yaml",
        "gate_evidence": legacy._gate_evidence(publish),
    }
    if (publish / "diff.patch").is_file():
        evidence["diff"] = "diff.patch"
    if (publish / "metrics.json").is_file():
        evidence["metrics_ref"] = "metrics.json"
    if (publish / "codex-events.jsonl").is_file():
        evidence["codex_events_ref"] = "codex-events.jsonl"
    if (publish / "codex-stderr.txt").is_file():
        evidence["codex_stderr_ref"] = "codex-stderr.txt"

    runtime = metadata.get("runtime", {}) or {}
    if not runtime:
        runtime = adapter_runtime
    envelope = {
        "schema_version": "1.1",
        "run_id": str(request.get("run_id") or ""),
        "golden_task_id": str(request.get("golden_task_id") or ""),
        "execution_owner": {"repository": legacy.EXECUTION_OWNER, "revision": revision},
        "unityagent": {
            "repository": legacy.UNITYAGENT_REPOSITORY,
            "revision": str(request.get("unityagent_revision") or ""),
        },
        "executor": {
            "profile": str((request.get("execution", {}) or {}).get("profile") or ""),
            "mode": mode,
            "execution_class": str(metadata.get("execution_class") or "unavailable"),
            "agent_id": str(metadata.get("agent_id") or "unavailable"),
            "provider": provider,
            "model": model,
            "model_revision": model_revision,
        },
        "attempt": {
            "agent_attempt": 1,
            "infrastructure_attempts": max(1, int(metadata.get("infrastructure_attempts", 1))),
        },
        "status": status,
        "failure": {
            "class": failure_class,
            "reason": str(metadata.get("failure_reason") or ""),
            "observation_state": observation_state,
        } if failure_class else {"class": "", "reason": "", "observation_state": observation_state},
        "runtime": runtime,
        "evidence": evidence,
        "execution_fingerprint": {
            "unityagent_revision": str(request.get("unityagent_revision") or ""),
            "graph_engineering_revision": revision,
            "golden_suite_revision": str(request.get("unityagent_revision") or ""),
            "execution_profile": str((request.get("execution", {}) or {}).get("profile") or ""),
            "execution_mode": mode,
            "provider": provider,
            "model": model,
            "reasoning_effort": str(metadata.get("reasoning_effort") or "unavailable"),
            "tool_manifest_hash": str(metadata.get("tool_manifest_hash") or legacy._command_hash(command)),
            "workspace_fixture_hash": fixture_hash,
        },
    }
    (publish / "execution-envelope.yaml").write_text(
        yaml.safe_dump(envelope, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--unityagent-root", type=Path, default=None)
    parser.add_argument("--agent-command-json", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=150.0)
    parser.add_argument("--require-production-identity", action="store_true")
    args = parser.parse_args()

    try:
        if args.timeout_seconds <= 0:
            raise legacy.BehaviorAdapterError("--timeout-seconds must be greater than zero")
        request = legacy._load_yaml(args.request)
        unityagent_root = legacy._resolve_unityagent_root(args.unityagent_root)
        fixture, mode, work_kind = legacy._validate_request(request, unityagent_root)
        command = legacy._load_command(args.agent_command_json)
        legacy._assert_clean_output(args.output)
        fixture_hash = legacy._hash_tree(fixture)

        with tempfile.TemporaryDirectory(prefix="unityagent-behavior-v2-") as temp_dir:
            temp = Path(temp_dir)
            sandbox = temp / "workspace"
            staging = temp / "evidence"
            publish = temp / "publish"
            shutil.copytree(fixture, sandbox)
            staging.mkdir(parents=True)
            publish.mkdir(parents=True)

            workspace = request.get("workspace", {}) or {}
            production_request = {
                "schema_version": "1.0",
                "task": request.get("task", {}) or {},
                "execution": {
                    "mode": mode,
                    "profile": str((request.get("execution", {}) or {}).get("profile") or ""),
                    "work_kind": work_kind,
                    "max_agent_attempts": 1,
                },
                "workspace_root": str(sandbox),
                "mutation_scope": {
                    "allowed_paths": legacy._scope_paths(workspace, "allowed_paths"),
                    "prohibited_paths": legacy._scope_paths(workspace, "prohibited_paths"),
                },
                "evidence_contract": request.get("evidence", {}) or {},
                "observed_evidence": request.get("observed_evidence", []) or [],
                "primary_focus": str(request.get("primary_focus") or ""),
                "evidence_output": str(staging),
                "unityagent_revision": str(request.get("unityagent_revision") or ""),
                "golden_task_id": str(request.get("golden_task_id") or ""),
            }
            production_request_path = temp / "production-request.json"
            production_request_path.write_text(
                json.dumps(production_request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

            process = run_streaming_process(
                [*command, "--request", str(production_request_path), "--output", str(staging)],
                cwd=legacy.ROOT,
                timeout_seconds=args.timeout_seconds,
                stdout_path=publish / "executor-stdout.txt",
                stderr_path=publish / "executor-stderr.txt",
                env=utf8_child_env(),
            )
            adapter_runtime = {
                "timeout_seconds": args.timeout_seconds,
                "root_pid": process.root_pid,
                "process_tree_cleanup": process.process_tree_cleanup,
                "remaining_processes": process.remaining_processes,
                "duration_seconds": process.duration_seconds,
                "first_output_latency_seconds": process.first_output_latency_seconds,
                "event_count": process.event_count,
                "last_event_timestamp": process.last_event_timestamp,
            }
            if process.timed_out:
                _ensure_failure_bundle(
                    staging, request,
                    f"Production Agent command timed out after {args.timeout_seconds:g} seconds",
                    "runtime_timeout",
                )

            _copy_bundle(staging, publish)
            metadata = legacy._metadata(staging)
            if args.require_production_identity and not process.timed_out:
                legacy._validate_production_identity(metadata)
            _write_envelope_v2(
                request, publish, command=command, fixture_hash=fixture_hash, mode=mode,
                metadata=metadata, process_returncode=(124 if process.timed_out else process.returncode),
                adapter_runtime=adapter_runtime,
            )
            legacy._publish_bundle(publish, args.output)
        return 0
    except (OSError, UnicodeError, yaml.YAMLError, json.JSONDecodeError, legacy.BehaviorAdapterError, ValueError) as exc:
        print(f"Behavior Eval Adapter v2 failed: {exc}", file=sys.stderr)
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
