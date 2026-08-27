#!/usr/bin/env python3
"""Bridge UnityAgent Behavior Eval requests to a production Agent command.

The adapter owns sandboxing, protocol vocabulary mapping, evidence transport, and
execution-envelope creation. It does not own provider policy, retries, or model runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
EXECUTION_OWNER = "DarumaPPAP/Unity-Graph-Engineering"
UNITYAGENT_REPOSITORY = "DarumaPPAP/UnityAgent"
MODE_MAP = {"prompt": "prompt", "graph_loop": "graph_loop"}
WORK_KIND_MAP = {
    "implementation": "mutation",
    "mutation": "mutation",
    "analysis": "analysis",
    "verification": "verification",
    "portable_import": "portable_import",
}
REQUIRED_EVIDENCE = ("response.md", "context-manifest.yaml", "artifact-index.yaml")
OPTIONAL_EVIDENCE = ("diff.patch", "gate-evidence.yaml", "metrics.json")
DEFAULT_EXECUTION_TIMEOUT_SECONDS = 900.0
MANAGED_OUTPUT_NAMES = (
    *REQUIRED_EVIDENCE,
    *OPTIONAL_EVIDENCE,
    "generated",
    "execution-envelope.yaml",
    "executor-stdout.txt",
    "executor-stderr.txt",
)


class BehaviorAdapterError(ValueError):
    """Behavior Eval adapter protocol violation."""


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise BehaviorAdapterError(f"Expected mapping: {path}")
    return data


def _git_revision(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
        shell=False,
    )
    revision = completed.stdout.strip() if completed.returncode == 0 else ""
    return revision or "unavailable"


def _hash_file(path: Path, digest: "hashlib._Hash") -> None:
    digest.update(path.name.encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        _hash_file(path, digest)
    return digest.hexdigest()


def _command_hash(command: list[str]) -> str:
    return hashlib.sha256(json.dumps(command, separators=(",", ":")).encode("utf-8")).hexdigest()


def _validate_request(request: dict[str, Any], unityagent_root: Path) -> tuple[Path, str, str]:
    if request.get("schema_version") != "1.0":
        raise BehaviorAdapterError("Behavior Eval request schema_version must be 1.0")
    if "expectation" in request:
        raise BehaviorAdapterError("Golden expectation must not be sent to production execution")

    execution = request.get("execution", {}) or {}
    mode = str(execution.get("mode") or "")
    work_kind = str(execution.get("work_kind") or "")
    if mode not in MODE_MAP:
        raise BehaviorAdapterError(f"Unsupported production execution mode: {mode}")
    if work_kind not in WORK_KIND_MAP:
        raise BehaviorAdapterError(f"Unsupported Behavior Eval work_kind: {work_kind}")
    if int(execution.get("max_agent_attempts", 0)) != 1:
        raise BehaviorAdapterError("Behavior Eval smoke execution must use exactly one Agent attempt")

    workspace = request.get("workspace", {}) or {}
    if workspace.get("mutation_mode") != "sandbox":
        raise BehaviorAdapterError("Behavior Eval mutation_mode must be sandbox")
    fixture_ref = Path(str(workspace.get("fixture") or ""))
    if fixture_ref.is_absolute() or ".." in fixture_ref.parts:
        raise BehaviorAdapterError("Behavior Eval fixture must be repository-relative without traversal")
    fixture = (unityagent_root / fixture_ref).resolve()
    allowed_root = (unityagent_root / "Tests" / "BehaviorEval" / "Fixtures").resolve()
    try:
        fixture.relative_to(allowed_root)
    except ValueError as exc:
        raise BehaviorAdapterError("Behavior Eval fixture is outside UnityAgent fixture root") from exc
    if not fixture.is_dir():
        raise BehaviorAdapterError(f"Behavior Eval fixture does not exist: {fixture_ref}")
    return fixture, MODE_MAP[mode], WORK_KIND_MAP[work_kind]


def _load_command(cli_value: str | None) -> list[str]:
    raw = cli_value or os.environ.get("UNITYAGENT_PRODUCTION_COMMAND_JSON", "")
    if not raw:
        raise BehaviorAdapterError(
            "Production Agent command is required via --agent-command-json or UNITYAGENT_PRODUCTION_COMMAND_JSON"
        )
    try:
        command = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BehaviorAdapterError("Production Agent command must be a JSON array") from exc
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        raise BehaviorAdapterError("Production Agent command must be a non-empty JSON string array")
    return command


def _assert_clean_output(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    collisions = sorted(name for name in MANAGED_OUTPUT_NAMES if (output / name).exists())
    if collisions:
        joined = ", ".join(collisions)
        raise BehaviorAdapterError(
            f"Behavior Eval output must be fresh; managed artifacts already exist: {joined}"
        )


def _copy_evidence(staging: Path, output: Path) -> None:
    for name in REQUIRED_EVIDENCE:
        source = staging / name
        if not source.is_file():
            raise BehaviorAdapterError(f"Production execution did not emit required evidence: {name}")
        shutil.copy2(source, output / name)

    for name in OPTIONAL_EVIDENCE:
        source = staging / name
        if source.is_file():
            shutil.copy2(source, output / name)

    generated = staging / "generated"
    if generated.is_dir():
        shutil.copytree(generated, output / "generated")


def _metadata(staging: Path) -> dict[str, Any]:
    path = staging / "execution-metadata.yaml"
    if not path.is_file():
        return {}
    return _load_yaml(path)


def _gate_evidence(output: Path) -> list[dict[str, Any]]:
    path = output / "gate-evidence.yaml"
    if not path.is_file():
        return []
    data = _load_yaml(path)
    items = data.get("gates", []) or data.get("gate_evidence", []) or []
    return [item for item in items if isinstance(item, dict)]


def _resolved_status(metadata: dict[str, Any], process_returncode: int) -> str:
    if process_returncode != 0:
        return "failed"
    requested_status = str(metadata.get("status") or "")
    if requested_status in {"completed", "unavailable", "failed"}:
        return requested_status
    return "completed"


def _write_envelope(
    request: dict[str, Any],
    output: Path,
    *,
    command: list[str],
    fixture_hash: str,
    mode: str,
    metadata: dict[str, Any],
    process_returncode: int,
) -> None:
    revision = _git_revision(ROOT)
    provider = str(metadata.get("provider") or "unavailable")
    model = str(metadata.get("model") or "unavailable")
    model_revision = str(metadata.get("model_revision") or "unavailable")
    infrastructure_attempts = max(1, int(metadata.get("infrastructure_attempts", 1)))
    status = _resolved_status(metadata, process_returncode)

    evidence: dict[str, Any] = {
        "context_manifest": "context-manifest.yaml",
        "response": "response.md",
        "artifact_index": "artifact-index.yaml",
        "gate_evidence": _gate_evidence(output),
    }
    if (output / "diff.patch").is_file():
        evidence["diff"] = "diff.patch"
    if (output / "metrics.json").is_file():
        evidence["metrics_ref"] = "metrics.json"

    envelope = {
        "schema_version": "1.0",
        "run_id": str(request.get("run_id") or ""),
        "golden_task_id": str(request.get("golden_task_id") or ""),
        "execution_owner": {
            "repository": EXECUTION_OWNER,
            "revision": revision,
        },
        "unityagent": {
            "repository": UNITYAGENT_REPOSITORY,
            "revision": str(request.get("unityagent_revision") or ""),
        },
        "executor": {
            "profile": str((request.get("execution", {}) or {}).get("profile") or ""),
            "mode": mode,
            "provider": provider,
            "model": model,
            "model_revision": model_revision,
        },
        "attempt": {
            "agent_attempt": 1,
            "infrastructure_attempts": infrastructure_attempts,
        },
        "status": status,
        "evidence": evidence,
        "execution_fingerprint": {
            "unityagent_revision": str(request.get("unityagent_revision") or ""),
            "graph_engineering_revision": revision,
            "golden_suite_revision": str(request.get("unityagent_revision") or ""),
            "execution_profile": str((request.get("execution", {}) or {}).get("profile") or ""),
            "execution_mode": mode,
            "provider": provider,
            "model": model,
            "tool_manifest_hash": str(metadata.get("tool_manifest_hash") or _command_hash(command)),
            "workspace_fixture_hash": fixture_hash,
        },
    }
    (output / "execution-envelope.yaml").write_text(
        yaml.safe_dump(envelope, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _publish_bundle(staged_output: Path, output: Path) -> None:
    for source in sorted(staged_output.iterdir(), key=lambda item: item.name):
        destination = output / source.name
        if destination.exists():
            raise BehaviorAdapterError(f"Refusing to overwrite Behavior Eval artifact: {destination.name}")
        shutil.move(str(source), str(destination))


def _resolve_unityagent_root(cli_root: Path | None) -> Path:
    if cli_root is not None:
        root = cli_root.resolve()
    else:
        raw = os.environ.get("UNITYAGENT_ROOT", "").strip()
        if not raw:
            raise BehaviorAdapterError("UnityAgent checkout root is required via --unityagent-root or UNITYAGENT_ROOT")
        root = Path(raw).resolve()
    if not root.is_dir():
        raise BehaviorAdapterError(f"UnityAgent checkout root does not exist: {root}")
    if not (root / "AGENTS.md").is_file() or not (root / ".ai").is_dir():
        raise BehaviorAdapterError("Configured UnityAgent root does not look like a UnityAgent checkout")
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--unityagent-root", type=Path, default=None)
    parser.add_argument("--agent-command-json", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_EXECUTION_TIMEOUT_SECONDS)
    args = parser.parse_args()

    try:
        if args.timeout_seconds <= 0:
            raise BehaviorAdapterError("--timeout-seconds must be greater than zero")

        request = _load_yaml(args.request)
        unityagent_root = _resolve_unityagent_root(args.unityagent_root)
        fixture, mode, work_kind = _validate_request(request, unityagent_root)
        command = _load_command(args.agent_command_json)

        _assert_clean_output(args.output)
        fixture_hash = _hash_tree(fixture)

        with tempfile.TemporaryDirectory(prefix="unityagent-behavior-") as temp_dir:
            temp = Path(temp_dir)
            sandbox = temp / "workspace"
            staging = temp / "evidence"
            publish = temp / "publish"
            shutil.copytree(fixture, sandbox)
            staging.mkdir(parents=True)
            publish.mkdir(parents=True)

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
                "evidence_output": str(staging),
                "unityagent_revision": str(request.get("unityagent_revision") or ""),
                "golden_task_id": str(request.get("golden_task_id") or ""),
            }
            production_request_path = temp / "production-request.json"
            production_request_path.write_text(
                json.dumps(production_request, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            try:
                completed = subprocess.run(
                    [*command, "--request", str(production_request_path), "--output", str(staging)],
                    cwd=ROOT,
                    check=False,
                    text=True,
                    capture_output=True,
                    shell=False,
                    timeout=args.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise BehaviorAdapterError(
                    f"Production Agent command timed out after {args.timeout_seconds:g} seconds"
                ) from exc

            (publish / "executor-stdout.txt").write_text(completed.stdout, encoding="utf-8")
            (publish / "executor-stderr.txt").write_text(completed.stderr, encoding="utf-8")
            _copy_evidence(staging, publish)
            metadata = _metadata(staging)
            _write_envelope(
                request,
                publish,
                command=command,
                fixture_hash=fixture_hash,
                mode=mode,
                metadata=metadata,
                process_returncode=completed.returncode,
            )
            _publish_bundle(publish, args.output)

        return 0
    except (OSError, UnicodeError, yaml.YAMLError, json.JSONDecodeError, BehaviorAdapterError, ValueError) as exc:
        print(f"Behavior Eval Adapter failed: {exc}", file=sys.stderr)
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
