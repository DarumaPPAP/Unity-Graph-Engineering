#!/usr/bin/env python3
"""Phase 1.1 hardened Codex Production Agent.

This v2 bridge keeps the original bridge intact while adding deterministic gate aggregation,
canonical policy provenance, UTF-8 streaming evidence, timeout tree cleanup, and pinned reasoning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

import codex_production_agent as legacy
from process_runtime import StreamingProcessResult, run_streaming_process, utf8_child_env

DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_REASONING_EFFORT = "high"
ROUTE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _recursive_has_key(value: Any, target: str) -> bool:
    if isinstance(value, dict):
        return target in value or any(_recursive_has_key(child, target) for child in value.values())
    if isinstance(value, list):
        return any(_recursive_has_key(child, target) for child in value)
    return False


def _source_in_control(control: Path, source_path: str) -> tuple[Path, str]:
    raw = source_path.replace("\\", "/").strip()
    prefix = legacy.CONTROL_DIR_NAME + "/"
    if raw.startswith(prefix):
        raw = raw[len(prefix):]
    path_text, _, fragment = raw.partition("#")
    pure = PurePosixPath(path_text)
    if not path_text or pure.is_absolute() or ".." in pure.parts:
        raise legacy.CodexProductionAgentError(f"Invalid policy source path: {source_path}")
    resolved = (control / Path(*pure.parts)).resolve()
    try:
        resolved.relative_to(control.resolve())
    except ValueError as exc:
        raise legacy.CodexProductionAgentError(f"Policy source escaped control snapshot: {source_path}") from exc
    return resolved, fragment


def _validate_policies(control: Path, structured: dict[str, Any]) -> None:
    normalized: list[dict[str, str]] = []
    for item in structured.get("loaded_policies", []) or []:
        if not isinstance(item, dict):
            raise legacy.CodexProductionAgentError("loaded_policies entries must be objects")
        policy_id = str(item.get("id") or "").strip()
        source_path = str(item.get("source_path") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not policy_id or not source_path or not reason:
            raise legacy.CodexProductionAgentError("loaded_policies requires canonical id/source_path/reason")
        source, fragment = _source_in_control(control, source_path)
        if fragment != policy_id:
            raise legacy.CodexProductionAgentError(
                f"Policy clause id/source fragment mismatch: {policy_id} vs {source_path}"
            )
        if not source.is_file() or source.suffix.lower() not in {".yaml", ".yml"}:
            raise legacy.CodexProductionAgentError(f"Policy source is not authoritative YAML: {source_path}")
        data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        if not _recursive_has_key(data, policy_id):
            raise legacy.CodexProductionAgentError(f"Unknown canonical policy clause: {policy_id}")
        normalized.append({
            "id": policy_id,
            "source_path": source_path,
            "reason": reason,
        })
    structured["loaded_policies"] = normalized


def _task_contract(control: Path, route: str) -> dict[str, Any]:
    if not ROUTE_RE.fullmatch(route):
        raise legacy.CodexProductionAgentError(f"Invalid or empty route: {route}")
    path = control / ".ai" / "harness" / "task-contracts" / f"{route}.yaml"
    if not path.is_file():
        raise legacy.CodexProductionAgentError(f"Task Contract unavailable for route: {route}")
    contract = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(contract, dict) or contract.get("id") != route:
        raise legacy.CodexProductionAgentError(f"Task Contract identity mismatch: {route}")
    return contract


def _trusted_evidence(request: dict[str, Any]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for item in request.get("observed_evidence", []) or []:
        if not isinstance(item, dict):
            raise legacy.CodexProductionAgentError("observed_evidence entries must be objects")
        gate = str(item.get("gate") or "").strip()
        status = str(item.get("status") or "").strip()
        if not gate or status not in {"passed", "failed", "unavailable"}:
            raise legacy.CodexProductionAgentError("Invalid trusted observed evidence")
        output.append({
            "gate": gate,
            "status": status,
            "evidence": str(item.get("statement") or item.get("id") or "fixture evidence"),
        })
    return output


def _resolve_gates(control: Path, request: dict[str, Any], structured: dict[str, Any]) -> str:
    route = str(structured.get("route") or "").strip()
    contract = _task_contract(control, route)
    required = {str(item) for item in contract.get("required_quality_gates", []) or []}
    conditional = {str(item) for item in contract.get("conditional_quality_gates", []) or []}
    by_id: dict[str, dict[str, str]] = {}

    for item in structured.get("quality_gates", []) or []:
        if not isinstance(item, dict):
            continue
        gate = str(item.get("id") or "").strip()
        if not gate:
            continue
        reported_requirement = str(item.get("requirement") or "informational").strip()
        status = str(item.get("status") or "unavailable").strip()
        if status not in {"passed", "failed", "unavailable"}:
            status = "unavailable"
        if gate in required:
            level = "required"
        elif gate in conditional and reported_requirement == "conditional":
            level = "conditional"
        elif gate in conditional:
            level = "not_applicable"
        else:
            level = "informational"
        by_id[gate] = {
            "id": gate,
            "requirement": level,
            "status": status,
            "evidence": str(item.get("evidence") or ""),
        }

    trusted = _trusted_evidence(request)
    for item in trusted:
        gate = item["gate"]
        level = "required" if gate in required else ("conditional" if gate in conditional else "informational")
        by_id[gate] = {
            "id": gate,
            "requirement": level,
            "status": item["status"],
            "evidence": item["evidence"],
        }

    for gate in required:
        if gate not in by_id:
            by_id[gate] = {
                "id": gate,
                "requirement": "required",
                "status": "unavailable",
                "evidence": "Required gate was not observed in this attempt.",
            }

    blocking = [item for item in by_id.values() if item["requirement"] in {"required", "conditional"}]
    if any(item["status"] == "failed" for item in blocking):
        status = "failed"
    elif any(item["status"] == "unavailable" for item in blocking):
        status = "unavailable"
    else:
        status = "passed"

    structured["quality_gates"] = [by_id[key] for key in sorted(by_id)]
    evidence = [item for item in structured.get("execution_evidence", []) or [] if isinstance(item, dict)]
    evidence.extend(trusted)
    structured["execution_evidence"] = evidence
    structured["execution_status"] = status
    return status


def _scope_error(request: dict[str, Any], changed: list[str]) -> str:
    execution = request.get("execution", {}) or {}
    work_kind = str(execution.get("work_kind") or "")
    allowed = legacy._normalized_scope(request, "allowed_paths")
    prohibited = legacy._normalized_scope(request, "prohibited_paths")
    if work_kind in {"analysis", "verification"} and changed:
        return "Non-mutating execution changed workspace files: " + ", ".join(changed)
    prohibited_hits = [path for path in changed if any(legacy._path_matches(path, scope) for scope in prohibited)]
    if prohibited_hits:
        return "Mutation touched prohibited paths: " + ", ".join(prohibited_hits)
    if allowed:
        outside = [path for path in changed if not any(legacy._path_matches(path, scope) for scope in allowed)]
        if outside:
            return "Mutation escaped allowed paths: " + ", ".join(outside)
    return ""


def _runtime(result: StreamingProcessResult, timeout: float) -> dict[str, Any]:
    return {
        "timeout_seconds": timeout,
        "root_pid": result.root_pid,
        "process_tree_cleanup": result.process_tree_cleanup,
        "remaining_processes": result.remaining_processes,
        "duration_seconds": result.duration_seconds,
        "first_output_latency_seconds": result.first_output_latency_seconds,
        "event_count": result.event_count,
        "last_event_timestamp": result.last_event_timestamp,
    }


def _context_metrics(control: Path, result: StreamingProcessResult | None = None) -> dict[str, Any]:
    files = [path for path in control.rglob("*") if path.is_file()]
    metrics: dict[str, Any] = {
        "control_snapshot_files": len(files),
        "total_input_bytes": sum(path.stat().st_size for path in files),
    }
    if result is not None:
        metrics.update({
            "codex_duration_seconds": result.duration_seconds,
            "first_output_latency_seconds": result.first_output_latency_seconds,
            "event_count": result.event_count,
        })
    return metrics


def _patch_metadata(output: Path, *, failure_class: str, reasoning_effort: str, runtime: dict[str, Any]) -> None:
    path = output / "execution-metadata.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not isinstance(data, dict):
        data = {}
    data["failure_class"] = failure_class
    data["reasoning_effort"] = reasoning_effort
    data["runtime"] = runtime
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_metrics(output: Path, *, failure_class: str, changed: list[str], context: dict[str, Any], runtime: dict[str, Any]) -> None:
    (output / "metrics.json").write_text(json.dumps({
        "failure_class": failure_class or None,
        "changed_paths": changed,
        "context_metrics": context,
        "runtime": runtime,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _prompt(request: dict[str, Any]) -> str:
    base = legacy._build_prompt(request)
    observed = request.get("observed_evidence", []) or []
    return base + f"""

PHASE 1.1 HARDENING CONTRACT
- `loaded_policies[].id` is a canonical policy CLAUSE id, never a document id.
- For a clause from user-policy use `source_path` with an exact fragment, for example `.ai/user-policy.yaml#minimum_cohesive_solution_first`.
- Quality gate `requirement` must be one of: required, conditional, informational, not_applicable.
- Use `conditional` only when that conditional gate is actually activated by this task. Otherwise use `not_applicable`.
- The bridge ignores your overall status guess and derives completion from the authoritative Task Contract selected by your own route.
- Trusted observed evidence below is input evidence, not a Golden answer. Do not rewrite or broaden it.

TRUSTED OBSERVED EVIDENCE
{json.dumps(observed, ensure_ascii=False, indent=2)}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codex-command-json", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT, choices=("low", "medium", "high", "xhigh"))
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--keep-mcp", action="store_true")
    args = parser.parse_args()

    provider = legacy.DEFAULT_PROVIDER
    model = "unavailable"
    version = "unavailable"
    tool_hash = hashlib.sha256(b"codex-production-agent-v2-unresolved").hexdigest()
    request: dict[str, Any] = {}
    control: Path | None = None

    try:
        if args.timeout_seconds <= 0:
            raise legacy.CodexProductionAgentError("--timeout-seconds must be greater than zero")
        request = legacy._load_request(args.request)
        workspace = legacy._resolve_workspace(request)
        unityagent_root = legacy._resolve_unityagent_root()
        command = legacy._load_command(args.codex_command_json)
        provider, model = legacy._resolve_identity(args.model)
        version = legacy._codex_version(command)
        tool_hash = hashlib.sha256(json.dumps({
            "command": command,
            "version": version,
            "provider": provider,
            "model": model,
            "reasoning_effort": args.reasoning_effort,
            "bridge": "v2",
        }, sort_keys=True).encode("utf-8")).hexdigest()

        control = legacy._copy_control_snapshot(unityagent_root, workspace)
        control_hash = legacy._hash_tree(control)
        before = legacy._snapshot_workspace(workspace)
        args.output.mkdir(parents=True, exist_ok=True)
        schema_path = args.output / "_codex-output.schema.json"
        final_path = args.output / "_codex-final.json"
        events_path = args.output / "codex-events.jsonl"
        stderr_path = args.output / "codex-stderr.txt"
        schema_path.write_text(json.dumps(legacy._output_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        codex_command = [
            *command, "exec", "--ephemeral", "--json", "--skip-git-repo-check",
            "--sandbox", "workspace-write", "--model", model,
            "-c", f'model_reasoning_effort="{args.reasoning_effort}"',
            "--output-schema", str(schema_path), "--output-last-message", str(final_path),
            "--cd", str(workspace),
        ]
        if not args.keep_mcp:
            codex_command.extend(["-c", "features.rmcp_client=false"])
        codex_command.append(_prompt(request))

        process = run_streaming_process(
            codex_command,
            cwd=workspace,
            timeout_seconds=args.timeout_seconds,
            stdout_path=events_path,
            stderr_path=stderr_path,
            env=utf8_child_env(),
        )
        runtime = _runtime(process, args.timeout_seconds)
        context = _context_metrics(control, process)

        if process.timed_out:
            message = f"Codex CLI timed out after {args.timeout_seconds:g} seconds"
            legacy._write_failure_evidence(
                request, args.output, message=message, provider=provider, model=model,
                version=version, tool_hash=tool_hash,
            )
            _patch_metadata(args.output, failure_class="runtime_timeout", reasoning_effort=args.reasoning_effort, runtime=runtime)
            _write_metrics(args.output, failure_class="runtime_timeout", changed=[], context=context, runtime=runtime)
            print(message, file=sys.stderr)
            return 124

        after = legacy._snapshot_workspace(workspace)
        changed = legacy._changed_paths(before, after)
        if legacy._hash_tree(control) != control_hash:
            raise legacy.CodexProductionAgentError("Codex modified the reserved UnityAgent control snapshot")

        if process.returncode != 0:
            message = f"Codex CLI failed with exit code {process.returncode}."
            if process.stderr.strip():
                message += "\n" + process.stderr.strip()
            legacy._write_failure_evidence(
                request, args.output, message=message, provider=provider, model=model,
                version=version, tool_hash=tool_hash,
            )
            _patch_metadata(args.output, failure_class="runtime_protocol_failure", reasoning_effort=args.reasoning_effort, runtime=runtime)
            _write_metrics(args.output, failure_class="runtime_protocol_failure", changed=changed, context=context, runtime=runtime)
            return process.returncode

        if not final_path.is_file():
            raise legacy.CodexProductionAgentError("Codex CLI did not emit structured final evidence")
        structured = json.loads(final_path.read_text(encoding="utf-8"))
        if not isinstance(structured, dict):
            raise legacy.CodexProductionAgentError("Codex structured final output must be a JSON object")

        _validate_policies(control, structured)
        _resolve_gates(control, request, structured)
        scope_error = _scope_error(request, changed)
        failure_class = "agent_behavior_regression" if scope_error else ""
        if scope_error:
            structured["execution_status"] = "failed"
            response = str(structured.get("response_markdown") or "").rstrip()
            structured["response_markdown"] = (response + "\n\n" if response else "") + f"Mutation scope violation: {scope_error}"

        legacy._write_success_evidence(
            request, args.output, structured, provider=provider, model=model, version=version,
            tool_hash=tool_hash, workspace=workspace, before=before, after=after, changed=changed,
        )
        _patch_metadata(args.output, failure_class=failure_class, reasoning_effort=args.reasoning_effort, runtime=runtime)
        _write_metrics(args.output, failure_class=failure_class, changed=changed, context=context, runtime=runtime)
        return 10 if scope_error else 0

    except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError, legacy.CodexProductionAgentError, ValueError) as exc:
        message = f"Codex Production Agent v2 failed: {exc}"
        try:
            if request and model != "unavailable":
                legacy._write_failure_evidence(
                    request, args.output, message=message, provider=provider, model=model,
                    version=version, tool_hash=tool_hash,
                )
                _patch_metadata(args.output, failure_class="runtime_protocol_failure", reasoning_effort=args.reasoning_effort, runtime={})
        except OSError:
            pass
        print(message, file=sys.stderr)
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
