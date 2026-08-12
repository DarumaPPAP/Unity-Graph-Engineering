#!/usr/bin/env python3
"""Execution Orchestrator for Unity Graph Engineering.

The orchestrator composes fixed JSON contracts only. It coordinates
Continuation, optional Ix navigation, direct source verification, Layered
Memory, evidence admission and quota accounting, but owns none of their
underlying authorities.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.1"
PROFILES = {"generic_planning", "personal_full_control", "team_safe_import"}
WORK_KINDS = {"mutation", "verification", "analysis"}
SAFE_NON_PERSONAL_SCOPES = {"portable_artifact", "public_reference"}
IX_OPERATIONS = {"explain", "impact", "trace", "callers", "callees"}
DEFAULT_CONTROLLER_TIMEOUT = 20
DEFAULT_MEMORY_TIMEOUT = 30
DEFAULT_IX_TIMEOUT = 45
MAX_MEMORY_ITEMS = 8
MAX_MEMORY_CHARS = 6000

ROOT = Path(__file__).resolve().parents[2]
CONTINUATION_CONTROLLER = ROOT / "Tools" / "ContinuationController" / "continuation_controller.py"
MEMORY_CONTROLLER = ROOT / "Tools" / "LayeredMemoryController" / "layered_memory_controller.py"
IX_ADAPTER = ROOT / "Tools" / "IxAdapter" / "ix_adapter.py"


class OrchestrationError(Exception):
    def __init__(self, code: str, message: str, status: str = "blocked") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OrchestrationError("invalid_request", f"{name} must be an object", "invalid_request")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrchestrationError("invalid_request", f"{name} must be a non-empty string", "invalid_request")
    return value.strip()


def _profile(request: dict[str, Any]) -> str:
    profile = str(request.get("execution_profile", "")).strip()
    if profile not in PROFILES:
        raise OrchestrationError(
            "invalid_profile",
            f"execution_profile must be one of {sorted(PROFILES)}",
            "invalid_request",
        )
    return profile


def _workspace(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise OrchestrationError("workspace_not_found", f"workspace does not exist: {path}", "invalid_request")
    return path


def _path_under_workspace(workspace: Path, value: str, field: str, *, require_file: bool) -> Path:
    raw = Path(value)
    candidate = raw if raw.is_absolute() else workspace / raw
    resolved = candidate.expanduser().resolve()
    if resolved != workspace and workspace not in resolved.parents:
        raise OrchestrationError("path_escape_forbidden", f"{field} escapes workspace: {value}")
    if require_file and not resolved.is_file():
        raise OrchestrationError("file_not_found", f"{field} is not a file: {value}", "invalid_request")
    return resolved


def _workspace_relative(workspace: Path, path: Path) -> str:
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError as exc:
        raise OrchestrationError("path_escape_forbidden", f"path escapes workspace: {path}") from exc


def _run_json(
    command: list[str],
    payload: dict[str, Any] | None,
    *,
    timeout: int,
    expected_identity: tuple[str, str] | None = None,
) -> dict[str, Any]:
    if timeout <= 0:
        raise OrchestrationError("invalid_timeout", "controller timeout must be greater than zero", "invalid_request")
    if not command:
        raise OrchestrationError("invalid_command", "controller command must not be empty", "invalid_request")
    try:
        completed = subprocess.run(
            command,
            input=None if payload is None else json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise OrchestrationError("controller_timeout", "controller invocation timed out") from exc
    except OSError as exc:
        raise OrchestrationError("controller_launch_failed", str(exc)) from exc

    stdout = (completed.stdout or "").strip()
    try:
        result = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as exc:
        raise OrchestrationError(
            "controller_non_json",
            f"controller returned non-JSON output (exit {completed.returncode})",
        ) from exc
    if not isinstance(result, dict):
        raise OrchestrationError("controller_contract_breach", "controller result must be a JSON object")
    if expected_identity is not None:
        key, expected = expected_identity
        if result.get(key) != expected:
            raise OrchestrationError(
                "controller_identity_mismatch",
                f"expected {key}={expected}, got {result.get(key)!r}",
            )
    if completed.returncode != 0 and "status" not in result:
        raise OrchestrationError("controller_failed", f"controller exited {completed.returncode} without typed status")
    return result


def _continuation(
    operation: str,
    state: dict[str, Any],
    *,
    now: str | None = None,
    slots: int | None = None,
) -> dict[str, Any]:
    command = [sys.executable, str(CONTINUATION_CONTROLLER), operation, "--input", "-"]
    if operation in {"evaluate", "claim"} and now:
        command.extend(["--now", now])
    if operation == "spend":
        command.extend(["--slots", str(slots or 1)])
    return _run_json(
        command,
        state,
        timeout=DEFAULT_CONTROLLER_TIMEOUT,
        expected_identity=("controller", "native_continuation"),
    )


def _memory(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    return _run_json(
        [
            sys.executable,
            str(MEMORY_CONTROLLER),
            "--workspace-root",
            str(workspace),
            "--request",
            "-",
        ],
        request,
        timeout=DEFAULT_MEMORY_TIMEOUT,
        expected_identity=("controller", "layered_memory"),
    )


def _ix(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    operation = str(request.get("operation", "")).strip()
    if operation not in IX_OPERATIONS:
        raise OrchestrationError(
            "invalid_ix_operation",
            f"code_intelligence.operation must be one of {sorted(IX_OPERATIONS)}",
            "invalid_request",
        )
    target = _text(request.get("target"), "code_intelligence.target")
    command = [sys.executable, str(IX_ADAPTER), operation, target, "--repo-root", str(workspace)]
    if operation == "trace":
        depth = int(request.get("depth", 3))
        cap = int(request.get("cap", 100))
        if not 1 <= depth <= 5:
            raise OrchestrationError("invalid_trace_depth", "trace depth must be 1..5", "invalid_request")
        if not 1 <= cap <= 200:
            raise OrchestrationError("invalid_trace_cap", "trace cap must be 1..200", "invalid_request")
        command.extend(["--depth", str(depth), "--cap", str(cap)])
        direction = str(request.get("direction", "both"))
        if direction not in {"both", "upstream", "downstream"}:
            raise OrchestrationError("invalid_trace_direction", "trace direction is invalid", "invalid_request")
        command.extend(["--direction", direction])
        kind = request.get("kind")
        if kind:
            command.extend(["--kind", str(kind)])
    return _run_json(
        command,
        None,
        timeout=DEFAULT_IX_TIMEOUT,
        expected_identity=("provider", "ix"),
    )


def _ticket(
    *,
    profile: str,
    work_kind: str,
    state: dict[str, Any],
    decision: dict[str, Any],
    source_verification: dict[str, Any],
) -> dict[str, Any]:
    selected = _dict(decision.get("selected_todo"), "decision.selected_todo")
    todo_id = _text(selected.get("id"), "decision.selected_todo.id")
    goal_id = _text(state.get("goal_id"), "execution_state.goal_id")
    worker = state.get("worker") or {}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "goal_id": goal_id,
        "selected_todo_id": todo_id,
        "worker_id": str(worker.get("id", "single")),
        "execution_profile": profile,
        "work_kind": work_kind,
        "state_fingerprint": _digest(state),
        "source_verification": {
            "completed": bool(source_verification.get("completed", False)),
            "scope_class": source_verification.get("scope_class"),
            "paths": list(source_verification.get("paths", [])),
            "evidence_refs": list(source_verification.get("evidence_refs", [])),
        },
    }
    payload["ticket_id"] = f"ticket-{_digest(payload)[:24]}"
    payload["ticket_digest"] = _digest({k: v for k, v in payload.items() if k != "ticket_digest"})
    return payload


def _verify_ticket(ticket: dict[str, Any]) -> None:
    supplied = _text(ticket.get("ticket_digest"), "ticket.ticket_digest")
    computed = _digest({k: v for k, v in ticket.items() if k != "ticket_digest"})
    if supplied != computed:
        raise OrchestrationError("ticket_integrity_failed", "execution ticket digest does not match")


def _source_verification(
    workspace: Path,
    profile: str,
    work_kind: str,
    request: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    source = _dict(request.get("source_verification", {}), "source_verification")
    completed = bool(source.get("completed", False))
    scope = str(
        source.get(
            "scope_class",
            "project_internal" if profile == "personal_full_control" else "portable_artifact",
        )
    )
    paths_raw = source.get("paths", [])
    if not isinstance(paths_raw, list):
        raise OrchestrationError("invalid_request", "source_verification.paths must be an array", "invalid_request")
    paths = [str(item).strip() for item in paths_raw if str(item).strip()]
    evidence_refs = source.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        raise OrchestrationError(
            "invalid_request",
            "source_verification.evidence_refs must be an array",
            "invalid_request",
        )
    evidence_refs = [str(item).strip() for item in evidence_refs if str(item).strip()]

    if profile != "personal_full_control" and scope not in SAFE_NON_PERSONAL_SCOPES:
        raise OrchestrationError(
            "source_scope_forbidden",
            f"{profile} may verify only {sorted(SAFE_NON_PERSONAL_SCOPES)} source scopes",
        )

    normalized_paths: list[str] = []
    if completed:
        if not paths:
            raise OrchestrationError(
                "source_verification_missing_paths",
                "completed source verification must name at least one explicitly-read path",
            )
        for value in paths:
            resolved = _path_under_workspace(
                workspace,
                value,
                "source_verification.paths[]",
                require_file=True,
            )
            normalized_paths.append(_workspace_relative(workspace, resolved))

    required = work_kind == "mutation" or bool(request.get("direct_source_read_required", False))
    if required and completed and not evidence_refs:
        raise OrchestrationError(
            "source_verification_evidence_missing",
            "mutation source verification requires at least one evidence_ref",
        )
    return (
        (not required) or completed,
        {
            "completed": completed,
            "required": required,
            "scope_class": scope,
            "paths": normalized_paths,
            "evidence_refs": evidence_refs,
        },
    )


def prepare(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    profile = _profile(request)
    state = _dict(request.get("execution_state"), "execution_state")
    if state.get("execution_mode") != "graph_loop":
        raise OrchestrationError("graph_loop_required", "Execution Orchestrator accepts graph_loop only", "invalid_request")
    _text(state.get("goal_id"), "execution_state.goal_id")
    state_profile = state.get("execution_profile")
    if state_profile is not None and state_profile != profile:
        raise OrchestrationError("profile_mismatch", "execution_state.execution_profile differs from request profile")

    work_kind = str(request.get("work_kind", "mutation"))
    if work_kind not in WORK_KINDS:
        raise OrchestrationError("invalid_work_kind", f"work_kind must be one of {sorted(WORK_KINDS)}", "invalid_request")
    now = request.get("now")
    diagnostics: list[dict[str, Any]] = []

    decision = _continuation("evaluate", state, now=str(now) if now else None)
    if decision.get("status") != "ok":
        return _envelope(
            "prepare",
            "blocked",
            ready=False,
            decision=decision,
            diagnostics=[{"code": "continuation_rejected", "message": "Continuation controller rejected the state."}],
        )
    if not decision.get("should_run", False):
        return _envelope(
            "prepare",
            "ok",
            ready=False,
            decision=decision,
            required_next_action=decision.get("effective_action", "none"),
        )

    selected = decision.get("selected_todo")
    if not isinstance(selected, dict) or not str(selected.get("id", "")).strip():
        return _envelope(
            "prepare",
            "ok",
            ready=False,
            decision=decision,
            required_next_action=decision.get("effective_action", "materialize_advancement_todo_or_blocker"),
            diagnostics=[
                {
                    "code": "selected_todo_required_for_ticket",
                    "message": "Runnable control-plane work must materialize a concrete selected todo before ticket issuance.",
                }
            ],
        )

    worker = state.get("worker") or {}
    multiple_workers = bool(worker.get("multiple_workers", False))
    if multiple_workers:
        claim_projection = _continuation("claim", state, now=str(now) if now else None)
        if claim_projection.get("status") != "ok":
            return _envelope(
                "prepare",
                "blocked",
                ready=False,
                decision=decision,
                claim=claim_projection,
                required_next_action="resolve_claim_failure",
            )
        existing = selected.get("lease") or {}
        projected = (claim_projection.get("claim") or {}).get("lease") or {}
        claim_confirmed = (
            bool(existing)
            and existing.get("id") == projected.get("id")
            and existing.get("owner") == worker.get("id")
        )
        if not claim_confirmed:
            return _envelope(
                "prepare",
                "ok",
                ready=False,
                decision=decision,
                claim=claim_projection,
                required_next_action="write_claim_to_authoritative_state",
                required_state_writeback={
                    "todo_id": claim_projection.get("todo_id"),
                    "claim": claim_projection.get("claim"),
                },
            )

    memory_projection = None
    memory_request = _dict(request.get("memory", {}), "memory")
    if bool(memory_request.get("enabled", False)):
        query = str(memory_request.get("query", "")).strip()
        if not query:
            diagnostics.append(
                {
                    "code": "memory_query_empty",
                    "message": "Broad empty-query memory loading is forbidden; projection was skipped.",
                }
            )
        else:
            memory_payload = {
                "operation": "project",
                "execution_profile": profile,
                "query": query,
                "max_items": min(max(1, int(memory_request.get("max_items", MAX_MEMORY_ITEMS))), MAX_MEMORY_ITEMS),
                "max_chars": min(max(256, int(memory_request.get("max_chars", MAX_MEMORY_CHARS))), MAX_MEMORY_CHARS),
                "repository": memory_request.get("repository"),
                "unity_version": memory_request.get("unity_version"),
                "platform": memory_request.get("platform"),
                "projection_id": memory_request.get("projection_id"),
            }
            memory_projection = _memory(workspace, memory_payload)
            if memory_projection.get("status") != "ok":
                diagnostics.append(
                    {
                        "code": "memory_unavailable",
                        "message": "Layered Memory projection failed; execution continues without memory context.",
                    }
                )
                memory_projection = None
            else:
                data = memory_projection.get("data") or {}
                if data.get("raw_content_included"):
                    raise OrchestrationError("memory_contract_breach", "memory project unexpectedly included raw content")
                if profile != "personal_full_control":
                    forbidden = [
                        item.get("memory_id")
                        for item in data.get("items", [])
                        if item.get("scope_class") not in SAFE_NON_PERSONAL_SCOPES
                    ]
                    if forbidden:
                        raise OrchestrationError("memory_scope_leak", "non-personal memory projection leaked forbidden scope")

    ix_result = None
    ix_request = _dict(request.get("code_intelligence", {}), "code_intelligence")
    if bool(ix_request.get("enabled", False)):
        if profile != "personal_full_control":
            diagnostics.append(
                {
                    "code": "ix_prohibited_for_profile",
                    "message": f"Ix was not invoked because execution_profile={profile}.",
                }
            )
        else:
            ix_result = _ix(workspace, ix_request)
            if ix_result.get("status") != "ok":
                diagnostics.append(
                    {
                        "code": "ix_fallback",
                        "message": "Ix is unavailable or failed; use targeted_source_read fallback.",
                    }
                )
            elif ix_result.get("low_confidence"):
                diagnostics.append(
                    {
                        "code": "ix_low_confidence",
                        "message": "Ix is low-confidence and may narrow navigation only.",
                    }
                )

    source_ready, source_projection = _source_verification(workspace, profile, work_kind, request)
    if not source_ready:
        return _envelope(
            "prepare",
            "ok",
            ready=False,
            decision=decision,
            memory=memory_projection,
            code_intelligence=ix_result,
            source_verification=source_projection,
            required_next_action="direct_source_read",
            diagnostics=diagnostics,
        )

    ticket = _ticket(
        profile=profile,
        work_kind=work_kind,
        state=state,
        decision=decision,
        source_verification=source_projection,
    )
    return _envelope(
        "prepare",
        "ok",
        ready=True,
        decision=decision,
        memory=memory_projection,
        code_intelligence=ix_result,
        source_verification=source_projection,
        ticket=ticket,
        required_next_action="execute_one_bounded_slice",
        diagnostics=diagnostics,
    )


def finalize(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    profile = _profile(request)
    state = _dict(request.get("execution_state"), "execution_state")
    ticket = _dict(request.get("ticket"), "ticket")
    _verify_ticket(ticket)
    if ticket.get("execution_profile") != profile:
        raise OrchestrationError("ticket_profile_mismatch", "ticket execution_profile differs from finalize request")
    if ticket.get("goal_id") != state.get("goal_id"):
        raise OrchestrationError("ticket_goal_mismatch", "ticket goal_id differs from execution state")

    result = _dict(request.get("slice_result"), "slice_result")
    slice_id = _text(result.get("slice_id"), "slice_result.slice_id")
    todo_id = _text(result.get("todo_id"), "slice_result.todo_id")
    if ticket.get("selected_todo_id") != todo_id:
        raise OrchestrationError("ticket_todo_mismatch", "slice_result.todo_id differs from prepared ticket")
    if result.get("writeback_complete") is not True:
        raise OrchestrationError("writeback_incomplete", "finalize requires writeback_complete=true")
    if result.get("validated") is not True:
        raise OrchestrationError("slice_unvalidated", "finalize requires validated=true")

    completed_at = _text(result.get("completed_at"), "slice_result.completed_at")
    evidence_id = _text(result.get("evidence_id"), "slice_result.evidence_id")
    evidence_path = _path_under_workspace(
        workspace,
        _text(result.get("evidence_file"), "slice_result.evidence_file"),
        "slice_result.evidence_file",
        require_file=True,
    )
    scope = str(
        result.get(
            "scope_class",
            "project_internal" if profile == "personal_full_control" else "portable_artifact",
        )
    )
    if profile != "personal_full_control" and scope not in SAFE_NON_PERSONAL_SCOPES:
        raise OrchestrationError("evidence_scope_forbidden", f"{profile} may finalize only safe evidence scopes")

    previous = _dict(state.get("previous_slice", {}), "execution_state.previous_slice")
    state_matches_ticket = _digest(state) == ticket.get("state_fingerprint")

    capture_request = {
        "operation": "capture_raw",
        "evidence_id": evidence_id,
        "source_file": str(evidence_path),
        "source_type": str(result.get("source_type", "verification_result")),
        "execution_profile": profile,
        "scope_class": scope,
        "created_at": completed_at,
        "statement": str(result.get("summary") or f"Evidence for {slice_id}"),
        "provenance": [slice_id, str(ticket.get("ticket_id"))],
        "repository": result.get("repository"),
        "unity_version": result.get("unity_version"),
        "platform": result.get("platform"),
        "run_id": state.get("run_id"),
        "sensitivity": str(result.get("sensitivity", "internal")),
        "tags": list(result.get("tags", [])) if isinstance(result.get("tags", []), list) else [],
    }
    capture = _memory(workspace, capture_request)
    if capture.get("status") != "ok":
        return _envelope(
            "finalize",
            "blocked",
            ready=False,
            evidence=capture,
            required_next_action="resolve_evidence_capture",
        )

    memory_records = [evidence_id]
    atom_projection = None
    atom = _dict(result.get("atom", {}), "slice_result.atom")
    if bool(atom.get("enabled", False)):
        atom_id = _text(atom.get("memory_id"), "slice_result.atom.memory_id")
        atom_projection = _memory(
            workspace,
            {
                "operation": "create_atom",
                "memory_id": atom_id,
                "statement": _text(atom.get("statement"), "slice_result.atom.statement"),
                "raw_refs": [evidence_id],
                "confidence": str(atom.get("confidence", "verified")),
                "execution_profile": profile,
                "scope_class": scope,
                "created_at": completed_at,
                "applicability": list(atom.get("applicability", [])) if isinstance(atom.get("applicability", []), list) else [],
                "limits": list(atom.get("limits", [])) if isinstance(atom.get("limits", []), list) else [],
                "provenance": [slice_id, evidence_id],
                "repository": result.get("repository"),
                "unity_version": result.get("unity_version"),
                "platform": result.get("platform"),
                "tags": list(result.get("tags", [])) if isinstance(result.get("tags", []), list) else [],
            },
        )
        if atom_projection.get("status") != "ok":
            return _envelope(
                "finalize",
                "blocked",
                ready=False,
                evidence=capture,
                atom=atom_projection,
                required_next_action="resolve_memory_atom",
            )
        memory_records.append(atom_id)

    if previous.get("quota_spent") is True and previous.get("slice_id") == slice_id:
        return _envelope(
            "finalize",
            "ok",
            ready=True,
            evidence=capture,
            atom=atom_projection,
            quota={
                "status": "ok",
                "operation": "spend",
                "spent_delta": 0,
                "idempotent_replay": True,
                "quota": state.get("quota", {}),
            },
            required_state_writeback={},
            diagnostics=[
                {
                    "code": "finalize_idempotent_replay",
                    "message": "Evidence was verified idempotently; quota was already spent for this slice.",
                }
            ],
        )

    if previous.get("quota_spent") is True and previous.get("slice_id") != slice_id:
        return _envelope(
            "finalize",
            "blocked",
            ready=False,
            evidence=capture,
            atom=atom_projection,
            required_next_action="reprepare_from_authoritative_state",
            diagnostics=[
                {
                    "code": "quota_accounting_conflict",
                    "message": "Authoritative state is already quota-accounted for a different slice; evidence was preserved.",
                }
            ],
        )

    if not state_matches_ticket:
        return _envelope(
            "finalize",
            "blocked",
            ready=False,
            evidence=capture,
            atom=atom_projection,
            required_next_action="reprepare_from_authoritative_state",
            diagnostics=[
                {
                    "code": "stale_execution_state",
                    "message": "Authoritative state changed after ticket issuance; evidence was preserved but quota/state accounting is blocked.",
                }
            ],
        )

    spend_state = copy.deepcopy(state)
    spend_previous = dict(spend_state.get("previous_slice") or {})
    spend_previous.update(
        {
            "slice_id": slice_id,
            "writeback_complete": True,
            "validated": True,
            "evidence_refs": list(dict.fromkeys([*list(spend_previous.get("evidence_refs", [])), evidence_id])),
        }
    )
    spend_state["previous_slice"] = spend_previous
    slots = int(result.get("slots", 1))
    if slots <= 0:
        raise OrchestrationError("invalid_slots", "slice_result.slots must be greater than zero", "invalid_request")

    spend = _continuation("spend", spend_state, slots=slots)
    if spend.get("status") != "ok":
        return _envelope(
            "finalize",
            "blocked",
            ready=False,
            evidence=capture,
            atom=atom_projection,
            quota=spend,
            required_next_action="resolve_quota_accounting",
            diagnostics=[
                {
                    "code": "evidence_preserved_without_quota_spend",
                    "message": "Evidence is durable but quota spend projection was rejected.",
                }
            ],
        )

    spend_id = f"spend-{_digest({'ticket': ticket.get('ticket_id'), 'slice': slice_id})[:24]}"
    required_state_writeback = {
        "previous_slice": {
            "slice_id": slice_id,
            "todo_id": todo_id,
            "writeback_complete": True,
            "validated": True,
            "evidence_refs": spend_state["previous_slice"]["evidence_refs"],
            "quota_spent": True,
            "quota_spend_id": spend_id,
            "orchestrated": True,
        },
        "quota": {"spent_slots": (spend.get("quota") or {}).get("spent_slots")},
        "orchestration": {
            "active_ticket_id": None,
            "last_quota_spend_id": spend_id,
            "required_next_action": "write_finalization_to_authoritative_state",
            "last_status": "ok",
        },
        "memory_projection": {
            "memory_ids": memory_records,
            "raw_evidence_refs": [evidence_id],
        },
    }
    return _envelope(
        "finalize",
        "ok",
        ready=True,
        evidence=capture,
        atom=atom_projection,
        quota=spend,
        required_state_writeback=required_state_writeback,
        required_next_action="write_finalization_to_authoritative_state",
    )


def _envelope(
    operation: str,
    status: str,
    *,
    ready: bool,
    decision: Any = None,
    claim: Any = None,
    memory: Any = None,
    code_intelligence: Any = None,
    source_verification: Any = None,
    ticket: Any = None,
    evidence: Any = None,
    atom: Any = None,
    quota: Any = None,
    required_state_writeback: Any = None,
    required_next_action: str | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "controller": "execution_orchestrator",
        "operation": operation,
        "status": status,
        "ready_for_execution": ready,
        "decision": decision,
        "claim": claim,
        "memory": memory,
        "code_intelligence": code_intelligence,
        "source_verification": source_verification,
        "ticket": ticket,
        "evidence": evidence,
        "atom": atom,
        "quota": quota,
        "required_state_writeback": required_state_writeback,
        "required_next_action": required_next_action,
        "diagnostics": diagnostics or [],
        "authority": {
            "owns_source_mutation": False,
            "owns_state_current": False,
            "owns_human_gate": False,
            "owns_quota_policy": False,
            "coordinates_controllers": True,
        },
    }


def execute(workspace: Path, operation: str, request: dict[str, Any]) -> dict[str, Any]:
    if operation == "prepare":
        return prepare(workspace, request)
    if operation == "finalize":
        return finalize(workspace, request)
    raise OrchestrationError("unsupported_operation", "operation must be prepare or finalize", "invalid_request")


def _read_input(value: str) -> dict[str, Any]:
    text = sys.stdin.read() if value == "-" else Path(value).expanduser().resolve().read_text(encoding="utf-8")
    return _dict(json.loads(text), "input")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compose Graph Engineering execution controllers safely.")
    parser.add_argument("operation", choices=["prepare", "finalize"])
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--input", default="-", help="Input JSON path or '-' for stdin.")
    args = parser.parse_args(argv)
    try:
        result = execute(_workspace(args.workspace_root), args.operation, _read_input(args.input))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        result = _envelope(
            args.operation,
            "invalid_request",
            ready=False,
            diagnostics=[{"code": "invalid_input", "message": str(exc)}],
        )
    except OrchestrationError as exc:
        result = _envelope(
            args.operation,
            exc.status,
            ready=False,
            diagnostics=[{"code": exc.code, "message": exc.message}],
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 4 if result["status"] == "invalid_request" else 3


if __name__ == "__main__":
    sys.exit(main())
