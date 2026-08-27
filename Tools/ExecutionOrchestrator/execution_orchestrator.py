#!/usr/bin/env python3
"""Fail-closed execution orchestrator for Unity Graph Engineering."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.3"
PROFILES = {"generic_planning", "personal_full_control", "team_safe_import"}
WORK_KINDS = {"mutation", "verification", "analysis", "portable_import"}
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


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise OrchestrationError("incomplete_control_state", f"{name} must be an explicit boolean")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OrchestrationError("incomplete_control_state", f"{name} must be numeric")
    return float(value)


def _profile(request: dict[str, Any]) -> str:
    profile = str(request.get("execution_profile", "")).strip()
    if profile not in PROFILES:
        raise OrchestrationError(
            "invalid_profile",
            f"execution_profile must be one of {sorted(PROFILES)}",
            "invalid_request",
        )
    return profile


def _validate_control_state(state: dict[str, Any], profile: str) -> None:
    """Require every safety-relevant field instead of inheriting permissive defaults."""
    if state.get("execution_mode") != "graph_loop":
        raise OrchestrationError(
            "graph_loop_required",
            "Execution Orchestrator accepts graph_loop only",
            "invalid_request",
        )
    if state.get("execution_profile") != profile:
        raise OrchestrationError(
            "profile_mismatch",
            "execution_state.execution_profile differs from request profile",
        )
    _text(state.get("goal_id"), "execution_state.goal_id")
    _bool(state.get("goal_complete"), "execution_state.goal_complete")

    health = _dict(state.get("health"), "execution_state.health")
    _bool(health.get("ok"), "execution_state.health.ok")
    human = _dict(state.get("human_gate"), "execution_state.human_gate")
    _bool(human.get("required"), "execution_state.human_gate.required")
    _bool(human.get("satisfied"), "execution_state.human_gate.satisfied")
    evidence_wait = _dict(state.get("evidence_wait"), "execution_state.evidence_wait")
    _bool(evidence_wait.get("waiting"), "execution_state.evidence_wait.waiting")
    focus_wait = _dict(state.get("focus_wait"), "execution_state.focus_wait")
    _bool(focus_wait.get("waiting"), "execution_state.focus_wait.waiting")

    budget = _dict(state.get("budget"), "execution_state.budget")
    _bool(budget.get("remaining"), "execution_state.budget.remaining")
    quota = _dict(state.get("quota"), "execution_state.quota")
    compute_share = _number(quota.get("compute_share"), "execution_state.quota.compute_share")
    allowed_slots = _number(quota.get("allowed_slots"), "execution_state.quota.allowed_slots")
    spent_slots = _number(quota.get("spent_slots"), "execution_state.quota.spent_slots")
    if not 0.0 <= compute_share <= 1.0 or allowed_slots < 0 or spent_slots < 0:
        raise OrchestrationError("invalid_control_state", "quota values are outside valid bounds")

    worker = _dict(state.get("worker"), "execution_state.worker")
    _text(worker.get("id"), "execution_state.worker.id")
    _bool(worker.get("multiple_workers"), "execution_state.worker.multiple_workers")
    if not isinstance(state.get("todos"), list):
        raise OrchestrationError(
            "incomplete_control_state",
            "execution_state.todos must be an explicit array",
        )
    _bool(state.get("todos_truncated"), "execution_state.todos_truncated")
    if not isinstance(state.get("available_capabilities"), list):
        raise OrchestrationError(
            "incomplete_control_state",
            "execution_state.available_capabilities must be an explicit array",
        )


def _validate_profile_work_kind(profile: str, work_kind: str, source_scope: str | None = None) -> None:
    if work_kind not in WORK_KINDS:
        raise OrchestrationError(
            "invalid_work_kind",
            f"work_kind must be one of {sorted(WORK_KINDS)}",
            "invalid_request",
        )
    if profile == "generic_planning" and work_kind in {"mutation", "portable_import"}:
        raise OrchestrationError(
            "work_kind_profile_forbidden",
            "generic_planning cannot execute mutation/import work",
        )
    if profile == "team_safe_import" and work_kind == "mutation":
        if source_scope == "project_internal":
            raise OrchestrationError(
                "source_scope_forbidden",
                "team_safe_import may not access project_internal source",
            )
        raise OrchestrationError(
            "work_kind_profile_forbidden",
            "team_safe_import cannot use general mutation; use portable_import",
        )
    if work_kind == "portable_import" and profile != "team_safe_import":
        raise OrchestrationError(
            "work_kind_profile_forbidden",
            "portable_import is reserved for team_safe_import",
        )


def _workspace(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise OrchestrationError(
            "workspace_not_found",
            f"workspace does not exist: {path}",
            "invalid_request",
        )
    return path


def _path_under_workspace(workspace: Path, value: str, field: str, *, require_file: bool) -> Path:
    raw = Path(value)
    resolved = (raw if raw.is_absolute() else workspace / raw).expanduser().resolve()
    if resolved != workspace and workspace not in resolved.parents:
        raise OrchestrationError("path_escape_forbidden", f"{field} escapes workspace: {value}")
    if require_file and not resolved.is_file():
        raise OrchestrationError(
            "file_not_found",
            f"{field} is not a file: {value}",
            "invalid_request",
        )
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
    if timeout <= 0 or not command:
        raise OrchestrationError(
            "invalid_controller_invocation",
            "controller command/timeout is invalid",
            "invalid_request",
        )
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

    try:
        result = json.loads((completed.stdout or "").strip() or "{}")
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
        raise OrchestrationError(
            "controller_failed",
            f"controller exited {completed.returncode} without typed status",
        )
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
    command = [
        sys.executable,
        str(IX_ADAPTER),
        operation,
        target,
        "--repo-root",
        str(workspace),
    ]
    if operation == "trace":
        depth = int(request.get("depth", 3))
        cap = int(request.get("cap", 100))
        if not 1 <= depth <= 5 or not 1 <= cap <= 200:
            raise OrchestrationError(
                "invalid_trace_bounds",
                "trace depth/cap exceeds orchestrator bounds",
                "invalid_request",
            )
        command.extend(["--depth", str(depth), "--cap", str(cap)])
        direction = str(request.get("direction", "both"))
        if direction not in {"both", "upstream", "downstream"}:
            raise OrchestrationError(
                "invalid_trace_direction",
                "trace direction is invalid",
                "invalid_request",
            )
        command.extend(["--direction", direction])
        if request.get("kind"):
            command.extend(["--kind", str(request["kind"])])
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
    payload = {
        "schema_version": SCHEMA_VERSION,
        "goal_id": _text(state.get("goal_id"), "execution_state.goal_id"),
        "selected_todo_id": _text(selected.get("id"), "decision.selected_todo.id"),
        "worker_id": _text((state.get("worker") or {}).get("id"), "execution_state.worker.id"),
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
    if supplied != _digest({k: v for k, v in ticket.items() if k != "ticket_digest"}):
        raise OrchestrationError("ticket_integrity_failed", "execution ticket digest does not match")


def _validate_ticket_semantics(ticket: dict[str, Any]) -> None:
    """Reject semantically invalid tickets even when an attacker recomputes the digest."""
    profile = str(ticket.get("execution_profile", "")).strip()
    work_kind = str(ticket.get("work_kind", "")).strip()
    source = _dict(ticket.get("source_verification"), "ticket.source_verification")
    scope = str(source.get("scope_class", "")).strip()
    paths = source.get("paths")
    evidence_refs = source.get("evidence_refs")
    completed = source.get("completed") is True

    if not isinstance(paths, list) or not isinstance(evidence_refs, list):
        raise OrchestrationError(
            "ticket_semantics_invalid",
            "ticket source_verification paths/evidence_refs must be arrays",
        )

    _validate_profile_work_kind(profile, work_kind, scope or None)

    if profile != "personal_full_control":
        if scope not in SAFE_NON_PERSONAL_SCOPES or paths:
            raise OrchestrationError(
                "ticket_semantics_invalid",
                "non-personal ticket may not contain project-internal scope or local source paths",
            )

    if work_kind == "mutation":
        if not completed or not paths or not evidence_refs:
            raise OrchestrationError(
                "ticket_semantics_invalid",
                "mutation ticket requires completed source verification, source paths, and evidence refs",
            )

    if work_kind == "portable_import":
        if (
            profile != "team_safe_import"
            or not completed
            or scope != "portable_artifact"
            or paths
            or not evidence_refs
        ):
            raise OrchestrationError(
                "ticket_semantics_invalid",
                "portable_import ticket requires team_safe_import portable evidence without local paths",
            )


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
    evidence_raw = source.get("evidence_refs", [])
    if not isinstance(paths_raw, list) or not isinstance(evidence_raw, list):
        raise OrchestrationError(
            "invalid_request",
            "source_verification paths/evidence_refs must be arrays",
            "invalid_request",
        )
    paths = [str(item).strip() for item in paths_raw if str(item).strip()]
    evidence_refs = [str(item).strip() for item in evidence_raw if str(item).strip()]

    if profile != "personal_full_control":
        if scope not in SAFE_NON_PERSONAL_SCOPES:
            raise OrchestrationError(
                "source_scope_forbidden",
                f"{profile} may verify only safe source scopes",
            )
        if paths:
            raise OrchestrationError(
                "non_personal_source_path_forbidden",
                f"{profile} may not verify local source paths; use external/portable evidence refs",
            )
    if work_kind == "portable_import" and scope != "portable_artifact":
        raise OrchestrationError(
            "portable_import_scope_forbidden",
            "portable_import requires portable_artifact scope",
        )

    normalized_paths: list[str] = []
    if completed and profile == "personal_full_control":
        if not paths:
            raise OrchestrationError(
                "source_verification_missing_paths",
                "personal completed source verification requires an explicit path",
            )
        for value in paths:
            normalized_paths.append(
                _workspace_relative(
                    workspace,
                    _path_under_workspace(
                        workspace,
                        value,
                        "source_verification.paths[]",
                        require_file=True,
                    ),
                )
            )

    required = work_kind in {"mutation", "portable_import"} or bool(
        request.get("direct_source_read_required", False)
    )
    if required and completed and not evidence_refs:
        raise OrchestrationError(
            "source_verification_evidence_missing",
            "required source/import verification needs an evidence_ref",
        )
    return (not required or completed), {
        "completed": completed,
        "required": required,
        "scope_class": scope,
        "paths": normalized_paths,
        "evidence_refs": evidence_refs,
    }


def prepare(workspace: Path, request: dict[str, Any]) -> dict[str, Any]:
    profile = _profile(request)
    state = _dict(request.get("execution_state"), "execution_state")
    _validate_control_state(state, profile)
    work_kind = str(request.get("work_kind", "mutation"))
    source_scope = str(
        _dict(request.get("source_verification", {}), "source_verification").get("scope_class", "")
    ) or None
    _validate_profile_work_kind(profile, work_kind, source_scope)
    now = request.get("now")
    diagnostics: list[dict[str, Any]] = []

    decision = _continuation("evaluate", state, now=str(now) if now else None)
    if decision.get("status") != "ok":
        return _envelope(
            "prepare",
            "blocked",
            ready=False,
            decision=decision,
            diagnostics=[
                {
                    "code": "continuation_rejected",
                    "message": "Continuation controller rejected the state.",
                }
            ],
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
            required_next_action=decision.get(
                "effective_action",
                "materialize_advancement_todo_or_blocker",
            ),
            diagnostics=[
                {
                    "code": "selected_todo_required_for_ticket",
                    "message": "A concrete selected todo is required before ticket issuance.",
                }
            ],
        )

    worker = state["worker"]
    if worker["multiple_workers"]:
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
            and existing.get("owner") == worker["id"]
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
                    "message": "Broad empty-query memory loading is forbidden; projection skipped.",
                }
            )
        else:
            memory_projection = _memory(
                workspace,
                {
                    "operation": "project",
                    "execution_profile": profile,
                    "query": query,
                    "max_items": min(
                        max(1, int(memory_request.get("max_items", MAX_MEMORY_ITEMS))),
                        MAX_MEMORY_ITEMS,
                    ),
                    "max_chars": min(
                        max(256, int(memory_request.get("max_chars", MAX_MEMORY_CHARS))),
                        MAX_MEMORY_CHARS,
                    ),
                    "repository": memory_request.get("repository"),
                    "unity_version": memory_request.get("unity_version"),
                    "platform": memory_request.get("platform"),
                    "projection_id": memory_request.get("projection_id"),
                },
            )
            if memory_projection.get("status") != "ok":
                diagnostics.append(
                    {
                        "code": "memory_unavailable",
                        "message": "Memory projection failed; continuing without memory context.",
                    }
                )
                memory_projection = None
            else:
                data = memory_projection.get("data") or {}
                if data.get("raw_content_included"):
                    raise OrchestrationError(
                        "memory_contract_breach",
                        "memory project unexpectedly included raw content",
                    )
                if profile != "personal_full_control" and any(
                    item.get("scope_class") not in SAFE_NON_PERSONAL_SCOPES
                    for item in data.get("items", [])
                ):
                    raise OrchestrationError(
                        "memory_scope_leak",
                        "non-personal memory projection leaked forbidden scope",
                    )

    ix_result = None
    ix_request = _dict(request.get("code_intelligence", {}), "code_intelligence")
    if bool(ix_request.get("enabled", False)):
        if profile != "personal_full_control":
            diagnostics.append(
                {
                    "code": "ix_prohibited_for_profile",
                    "message": f"Ix was not invoked for {profile}.",
                }
            )
        else:
            ix_result = _ix(workspace, ix_request)
            if ix_result.get("status") != "ok":
                diagnostics.append(
                    {
                        "code": "ix_fallback",
                        "message": "Ix failed/unavailable; use targeted_source_read.",
                    }
                )
            elif ix_result.get("low_confidence"):
                diagnostics.append(
                    {
                        "code": "ix_low_confidence",
                        "message": "Ix may narrow navigation only.",
                    }
                )

    source_ready, source_projection = _source_verification(
        workspace,
        profile,
        work_kind,
        request,
    )
    if not source_ready:
        action = (
            "verify_portable_import_evidence"
            if work_kind == "portable_import"
            else "direct_source_read"
        )
        return _envelope(
            "prepare",
            "ok",
            ready=False,
            decision=decision,
            memory=memory_projection,
            code_intelligence=ix_result,
            source_verification=source_projection,
            required_next_action=action,
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
    _validate_control_state(state, profile)
    ticket = _dict(request.get("ticket"), "ticket")
    _verify_ticket(ticket)
    _validate_ticket_semantics(ticket)
    if ticket.get("execution_profile") != profile:
        raise OrchestrationError(
            "ticket_profile_mismatch",
            "ticket profile differs from finalize request",
        )
    if ticket.get("goal_id") != state.get("goal_id"):
        raise OrchestrationError(
            "ticket_goal_mismatch",
            "ticket goal differs from authoritative state",
        )

    result = _dict(request.get("slice_result"), "slice_result")
    slice_id = _text(result.get("slice_id"), "slice_result.slice_id")
    todo_id = _text(result.get("todo_id"), "slice_result.todo_id")
    if ticket.get("selected_todo_id") != todo_id:
        raise OrchestrationError(
            "ticket_todo_mismatch",
            "slice todo differs from prepared ticket",
        )
    if result.get("writeback_complete") is not True:
        raise OrchestrationError(
            "writeback_incomplete",
            "finalize requires writeback_complete=true",
        )
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
        raise OrchestrationError(
            "evidence_scope_forbidden",
            f"{profile} may finalize only safe evidence scopes",
        )
    ticket_work_kind = str(ticket.get("work_kind", ""))
    if profile == "generic_planning" and ticket_work_kind in {"mutation", "portable_import"}:
        raise OrchestrationError(
            "ticket_work_kind_profile_forbidden",
            "ticket work kind is incompatible with generic_planning",
        )
    if profile == "team_safe_import" and ticket_work_kind == "mutation":
        raise OrchestrationError(
            "ticket_work_kind_profile_forbidden",
            "team_safe_import cannot finalize general mutation",
        )
    if ticket_work_kind == "portable_import" and (
        profile != "team_safe_import" or scope != "portable_artifact"
    ):
        raise OrchestrationError(
            "portable_import_scope_forbidden",
            "portable_import ticket/evidence scope mismatch",
        )

    previous = _dict(state.get("previous_slice", {}), "execution_state.previous_slice")
    state_matches_ticket = _digest(state) == ticket.get("state_fingerprint")
    capture = _memory(
        workspace,
        {
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
            "tags": (
                list(result.get("tags", []))
                if isinstance(result.get("tags", []), list)
                else []
            ),
        },
    )
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
                "applicability": (
                    list(atom.get("applicability", []))
                    if isinstance(atom.get("applicability", []), list)
                    else []
                ),
                "limits": (
                    list(atom.get("limits", []))
                    if isinstance(atom.get("limits", []), list)
                    else []
                ),
                "provenance": [slice_id, evidence_id],
                "repository": result.get("repository"),
                "unity_version": result.get("unity_version"),
                "platform": result.get("platform"),
                "tags": (
                    list(result.get("tags", []))
                    if isinstance(result.get("tags", []), list)
                    else []
                ),
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
                    "message": "Quota was already spent for this slice.",
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
                    "message": "A different slice is already accounted; new evidence was preserved.",
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
                    "message": "State changed after ticket issuance; evidence was preserved and accounting blocked.",
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
            "evidence_refs": list(
                dict.fromkeys(
                    [*list(spend_previous.get("evidence_refs", [])), evidence_id]
                )
            ),
        }
    )
    spend_state["previous_slice"] = spend_previous
    slots = int(result.get("slots", 1))
    if slots <= 0:
        raise OrchestrationError(
            "invalid_slots",
            "slice_result.slots must be greater than zero",
            "invalid_request",
        )
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
                    "message": "Evidence is durable but quota spend was rejected.",
                }
            ],
        )

    spend_id = f"spend-{_digest({'ticket': ticket.get('ticket_id'), 'slice': slice_id})[:24]}"
    state_patch = {
        "previous_slice": {
            "slice_id": slice_id,
            "todo_id": todo_id,
            "writeback_complete": True,
            "validated": True,
            "evidence_refs": spend_previous["evidence_refs"],
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
        required_state_writeback=state_patch,
        required_next_action="write_finalization_to_authoritative_state",
    )


def _envelope(
    operation: str,
    status: str,
    *,
    ready: bool,
    decision=None,
    claim=None,
    memory=None,
    code_intelligence=None,
    source_verification=None,
    ticket=None,
    evidence=None,
    atom=None,
    quota=None,
    required_state_writeback=None,
    required_next_action=None,
    diagnostics=None,
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
    raise OrchestrationError(
        "unsupported_operation",
        "operation must be prepare or finalize",
        "invalid_request",
    )


def _read_input(value: str) -> dict[str, Any]:
    text = (
        sys.stdin.read()
        if value == "-"
        else Path(value).expanduser().resolve().read_text(encoding="utf-8")
    )
    return _dict(json.loads(text), "input")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compose Graph Engineering execution controllers safely."
    )
    parser.add_argument("operation", choices=["prepare", "finalize"])
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--input", default="-", help="Input JSON path or '-' for stdin.")
    args = parser.parse_args(argv)
    try:
        result = execute(
            _workspace(args.workspace_root),
            args.operation,
            _read_input(args.input),
        )
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
