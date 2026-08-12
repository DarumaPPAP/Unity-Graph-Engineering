#!/usr/bin/env python3
"""Deterministic native continuation controller for Unity Graph Engineering.

The controller is intentionally runtime-neutral. It consumes a compact JSON
projection of the authoritative execution state and returns a machine-readable
decision. It never bypasses Human Gates, never owns the source-of-truth state,
and never spends quota before validated durable writeback.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
DEFAULT_WINDOW_HOURS = 24
DEFAULT_SLOT_MINUTES = 1
DEFAULT_LEASE_SECONDS = 900

TODO_STATUSES = {"unclaimed", "claimed", "running", "waiting", "completed", "blocked"}
TASK_CLASSES = {"advancement_task", "continuous_monitor"}
OWNER_HELD_CAPABILITIES = {"credentials", "production_access", "human_review"}


class ContractError(ValueError):
    """Raised when the controller input violates the native contract."""


def _parse_time(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    result = datetime.fromisoformat(text)
    if result.tzinfo is None:
        raise ContractError("timestamp must include an offset or Z")
    return result.astimezone(timezone.utc)


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be an object")
    return value


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractError(f"{name} must be an array")
    return value


def _require_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{name} must be a boolean")
    return value


def _require_non_empty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value.strip()


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be numeric")
    return float(value)


def _quota_projection(state: dict[str, Any]) -> dict[str, Any]:
    quota = _require_dict(state.get("quota", {}), "quota")
    compute_share = _number(quota.get("compute_share", 1.0), "quota.compute_share")
    if not 0.0 <= compute_share <= 1.0:
        raise ContractError("quota.compute_share must be between 0 and 1")

    window_hours = int(_number(quota.get("window_hours", DEFAULT_WINDOW_HOURS), "quota.window_hours"))
    slot_minutes = int(_number(quota.get("slot_minutes", DEFAULT_SLOT_MINUTES), "quota.slot_minutes"))
    spent_slots = int(_number(quota.get("spent_slots", 0), "quota.spent_slots"))

    if window_hours <= 0:
        raise ContractError("quota.window_hours must be greater than zero")
    if slot_minutes <= 0:
        raise ContractError("quota.slot_minutes must be greater than zero")
    if spent_slots < 0:
        raise ContractError("quota.spent_slots must not be negative")

    explicit_allowed = quota.get("allowed_slots")
    if explicit_allowed is None:
        total_slots = (window_hours * 60) // slot_minutes
        allowed_slots = int(total_slots * compute_share)
    else:
        allowed_slots = int(_number(explicit_allowed, "quota.allowed_slots"))
        if allowed_slots < 0:
            raise ContractError("quota.allowed_slots must not be negative")

    eligible = compute_share > 0.0 and spent_slots < allowed_slots
    if compute_share == 0.0:
        state_name = "paused"
        reason = "compute quota is zero; automatic continuation is paused"
    elif spent_slots >= allowed_slots:
        state_name = "throttled"
        reason = f"quota exhausted: {spent_slots}/{allowed_slots} slots spent"
    else:
        state_name = "eligible"
        reason = f"quota eligible: {spent_slots}/{allowed_slots} slots spent"

    return {
        "compute_share": compute_share,
        "window_hours": window_hours,
        "slot_minutes": slot_minutes,
        "allowed_slots": allowed_slots,
        "spent_slots": spent_slots,
        "eligible": eligible,
        "state": state_name,
        "reason": reason,
    }


def _base_result(
    *,
    decision: str,
    lane: str,
    reason_code: str,
    reason: str,
    quota: dict[str, Any],
    should_run: bool = False,
    effective_action: str = "none",
    must_attempt_work: bool = False,
    normal_delivery_allowed: bool = False,
    selected_todo: dict[str, Any] | None = None,
    runnable_candidates: list[dict[str, Any]] | None = None,
    blocked_candidates: list[dict[str, Any]] | None = None,
    capability_gate: dict[str, Any] | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "controller": "native_continuation",
        "status": "ok",
        "decision": decision,
        "should_run": should_run,
        "lane": lane,
        "reason_code": reason_code,
        "reason": reason,
        "effective_action": effective_action,
        "must_attempt_work": must_attempt_work,
        "normal_delivery_allowed": normal_delivery_allowed,
        "selected_todo": selected_todo,
        "runnable_candidates": runnable_candidates or [],
        "blocked_candidates": blocked_candidates or [],
        "capability_gate": capability_gate,
        "quota": quota,
        "diagnostics": diagnostics or [],
    }


def _lease_state(todo: dict[str, Any], worker_id: str, now: datetime) -> tuple[str, dict[str, Any] | None]:
    lease = todo.get("lease")
    if lease is None:
        return "free", None
    lease = _require_dict(lease, f"todo[{todo.get('id', '?')}].lease")
    owner = lease.get("owner")
    expires_at_raw = lease.get("expires_at")
    if not expires_at_raw:
        return ("owned_by_self" if owner == worker_id else "owned_by_other"), lease

    expires_at = _parse_time(str(expires_at_raw))
    if expires_at <= now:
        return "expired", lease
    if owner == worker_id:
        return "owned_by_self", lease
    return "owned_by_other", lease


def _validate_todo(todo: dict[str, Any], index: int) -> dict[str, Any]:
    todo_id = _require_non_empty_string(todo.get("id"), f"todos[{index}].id")
    status = todo.get("status", "unclaimed")
    if status not in TODO_STATUSES:
        raise ContractError(f"todos[{index}].status is invalid: {status}")
    task_class = todo.get("task_class", "advancement_task")
    if task_class not in TASK_CLASSES:
        raise ContractError(f"todos[{index}].task_class is invalid: {task_class}")
    required_capabilities = todo.get("required_capabilities", [])
    _require_list(required_capabilities, f"todos[{index}].required_capabilities")
    for capability in required_capabilities:
        _require_non_empty_string(capability, f"todos[{index}].required_capabilities[]")
    normalized = deepcopy(todo)
    normalized["id"] = todo_id
    normalized["status"] = status
    normalized["task_class"] = task_class
    normalized["required_capabilities"] = list(dict.fromkeys(required_capabilities))
    return normalized


def evaluate(state: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    state = _require_dict(state, "state")
    now = now or datetime.now(timezone.utc)

    execution_mode = state.get("execution_mode", "graph_loop")
    if execution_mode != "graph_loop":
        raise ContractError("continuation controller only accepts execution_mode=graph_loop")

    _require_non_empty_string(state.get("goal_id", "goal"), "goal_id")
    quota = _quota_projection(state)

    if _require_bool(state.get("goal_complete", False), "goal_complete"):
        return _base_result(
            decision="complete",
            lane="complete",
            reason_code="goal_complete",
            reason="goal is already complete",
            quota=quota,
        )

    health = _require_dict(state.get("health", {"ok": True}), "health")
    if not _require_bool(health.get("ok", True), "health.ok"):
        return _base_result(
            decision="blocked",
            lane="health_gate",
            reason_code="health_blocked",
            reason=str(health.get("reason") or "health or safety gate is blocking continuation"),
            quota=quota,
            effective_action="repair_or_escalate_health",
        )

    human = _require_dict(
        state.get("human_gate", {"required": False, "satisfied": True}),
        "human_gate",
    )
    human_required = _require_bool(human.get("required", False), "human_gate.required")
    human_satisfied = _require_bool(human.get("satisfied", not human_required), "human_gate.satisfied")
    if human_required and not human_satisfied:
        return _base_result(
            decision="ask_human",
            lane="human_gate",
            reason_code="human_gate_required",
            reason=str(human.get("reason") or "explicit human decision is required"),
            quota=quota,
            effective_action="request_human_decision",
        )

    previous = state.get("previous_slice")
    if previous is not None:
        previous = _require_dict(previous, "previous_slice")
        if not _require_bool(previous.get("writeback_complete", False), "previous_slice.writeback_complete"):
            return _base_result(
                decision="blocked",
                lane="evidence_wait",
                reason_code="writeback_incomplete",
                reason="previous bounded slice has not completed durable writeback",
                quota=quota,
                effective_action="complete_writeback",
            )
        if not _require_bool(previous.get("validated", False), "previous_slice.validated"):
            return _base_result(
                decision="wait",
                lane="evidence_wait",
                reason_code="previous_slice_unvalidated",
                reason="previous bounded slice is waiting for validation",
                quota=quota,
                effective_action="validate_previous_slice",
            )

    evidence_wait = _require_dict(state.get("evidence_wait", {"waiting": False}), "evidence_wait")
    if _require_bool(evidence_wait.get("waiting", False), "evidence_wait.waiting"):
        return _base_result(
            decision="wait",
            lane="evidence_wait",
            reason_code="evidence_wait",
            reason=str(evidence_wait.get("reason") or "required evidence is not available yet"),
            quota=quota,
            effective_action="wait_for_evidence",
        )

    focus_wait = _require_dict(state.get("focus_wait", {"waiting": False}), "focus_wait")
    if _require_bool(focus_wait.get("waiting", False), "focus_wait.waiting"):
        return _base_result(
            decision="wait",
            lane="focus_wait",
            reason_code="focus_wait",
            reason=str(focus_wait.get("reason") or "current delivery lane should remain quiet"),
            quota=quota,
            effective_action="wait_for_focus_transition",
        )

    budget = _require_dict(state.get("budget", {"remaining": True}), "budget")
    if not _require_bool(budget.get("remaining", True), "budget.remaining"):
        return _base_result(
            decision="blocked",
            lane="budget_guard",
            reason_code="budget_exhausted",
            reason=str(budget.get("reason") or "execution budget is exhausted"),
            quota=quota,
            effective_action="request_budget_or_replan",
        )

    if quota["compute_share"] == 0.0:
        return _base_result(
            decision="wait",
            lane="compute_quota",
            reason_code="quota_paused",
            reason=quota["reason"],
            quota=quota,
            effective_action="quota_pause",
        )
    if not quota["eligible"]:
        return _base_result(
            decision="wait",
            lane="compute_quota",
            reason_code="quota_exhausted",
            reason=quota["reason"],
            quota=quota,
            effective_action="wait_for_quota_window",
        )

    worker = _require_dict(state.get("worker", {"id": "single", "multiple_workers": False}), "worker")
    worker_id = _require_non_empty_string(worker.get("id", "single"), "worker.id")
    multiple_workers = _require_bool(worker.get("multiple_workers", False), "worker.multiple_workers")

    available_capabilities_raw = _require_list(
        state.get("available_capabilities", ["shell", "filesystem_read", "filesystem_write"]),
        "available_capabilities",
    )
    available_capabilities = {
        _require_non_empty_string(item, "available_capabilities[]")
        for item in available_capabilities_raw
    }

    todos_raw = _require_list(state.get("todos", []), "todos")
    todos = [_validate_todo(_require_dict(todo, f"todos[{i}]"), i) for i, todo in enumerate(todos_raw)]
    open_todos = [todo for todo in todos if todo["status"] not in {"completed", "blocked", "waiting"}]
    advancement = [todo for todo in open_todos if todo["task_class"] == "advancement_task"]
    monitors = [todo for todo in open_todos if todo["task_class"] == "continuous_monitor"]

    runnable: list[dict[str, Any]] = []
    blocked_candidates: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    for todo in advancement:
        lease_state, lease = _lease_state(todo, worker_id, now)
        if multiple_workers and lease_state == "owned_by_other":
            diagnostics.append(
                {
                    "code": "todo_leased_by_other",
                    "todo_id": todo["id"],
                    "lease_owner": lease.get("owner") if lease else None,
                }
            )
            continue

        missing = [cap for cap in todo["required_capabilities"] if cap not in available_capabilities]
        candidate = {
            "todo_id": todo["id"],
            "task_class": todo["task_class"],
            "lease_state": lease_state,
            "required_capabilities": todo["required_capabilities"],
            "missing_capabilities": missing,
        }
        if missing:
            blocked_candidates.append(candidate)
        else:
            runnable.append(candidate)

    if runnable:
        selected_id = runnable[0]["todo_id"]
        selected_todo = next(todo for todo in advancement if todo["id"] == selected_id)
        return _base_result(
            decision="run",
            should_run=True,
            lane="bounded_work",
            reason_code="advancement_todo_runnable",
            reason=f"advancement todo {selected_id} is runnable",
            quota=quota,
            effective_action="run_bounded_slice",
            must_attempt_work=True,
            normal_delivery_allowed=True,
            selected_todo=selected_todo,
            runnable_candidates=runnable,
            blocked_candidates=blocked_candidates,
            capability_gate={
                "action": "run",
                "required": selected_todo["required_capabilities"],
                "missing": [],
                "runnable_candidates": runnable,
                "blocked_candidates": blocked_candidates,
            },
            diagnostics=diagnostics,
        )

    if blocked_candidates:
        missing_union = sorted(
            {
                capability
                for candidate in blocked_candidates
                for capability in candidate["missing_capabilities"]
            }
        )
        owner_held = sorted(set(missing_union) & OWNER_HELD_CAPABILITIES)
        if owner_held:
            return _base_result(
                decision="ask_human",
                lane="human_gate",
                reason_code="owner_capability_required",
                reason=f"owner-held capability required: {', '.join(owner_held)}",
                quota=quota,
                effective_action="request_required_capability",
                blocked_candidates=blocked_candidates,
                capability_gate={
                    "action": "ask_owner",
                    "required": missing_union,
                    "missing": missing_union,
                    "runnable_candidates": [],
                    "blocked_candidates": blocked_candidates,
                },
                diagnostics=diagnostics,
            )
        return _base_result(
            decision="blocked",
            lane="bounded_work",
            reason_code="capability_repair_required",
            reason=f"no advancement todo is runnable; missing: {', '.join(missing_union)}",
            quota=quota,
            effective_action="capability_repair",
            must_attempt_work=True,
            normal_delivery_allowed=False,
            blocked_candidates=blocked_candidates,
            capability_gate={
                "action": "repair_bridge",
                "required": missing_union,
                "missing": missing_union,
                "runnable_candidates": [],
                "blocked_candidates": blocked_candidates,
            },
            diagnostics=diagnostics,
        )

    todos_truncated = _require_bool(state.get("todos_truncated", False), "todos_truncated")
    if todos_truncated:
        return _base_result(
            decision="run",
            should_run=True,
            lane="bounded_work",
            reason_code="hidden_todo_conservative_advance",
            reason="todo projection is truncated; hidden open work is treated as advancement",
            quota=quota,
            effective_action="materialize_advancement_todo_or_blocker",
            must_attempt_work=True,
            normal_delivery_allowed=False,
            diagnostics=diagnostics,
        )

    if monitors:
        return _base_result(
            decision="wait",
            lane="focus_wait",
            reason_code="monitor_quiet",
            reason="only continuous-monitor work remains and no material transition is reported",
            quota=quota,
            effective_action="monitor_quiet_skip",
            diagnostics=diagnostics,
        )

    return _base_result(
        decision="wait",
        lane="focus_wait",
        reason_code="no_executable_todo",
        reason="goal is incomplete but no executable advancement todo is visible",
        quota=quota,
        effective_action="materialize_todo_or_blocker",
        diagnostics=diagnostics,
    )


def claim(
    state: dict[str, Any],
    *,
    now: datetime | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> dict[str, Any]:
    if lease_seconds <= 0:
        raise ContractError("lease_seconds must be greater than zero")
    now = now or datetime.now(timezone.utc)
    decision = evaluate(state, now=now)
    if not decision["should_run"] or decision["selected_todo"] is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "controller": "native_continuation",
            "status": "invalid_transition",
            "operation": "claim",
            "reason": "current decision does not expose a claimable selected todo",
            "decision": decision,
        }

    worker = _require_dict(state.get("worker", {"id": "single", "multiple_workers": False}), "worker")
    worker_id = _require_non_empty_string(worker.get("id", "single"), "worker.id")
    todo = decision["selected_todo"]
    lease_state, existing_lease = _lease_state(todo, worker_id, now)

    if lease_state == "owned_by_self" and existing_lease is not None:
        lease = existing_lease
    else:
        lease = {
            "id": f"lease-{uuid.uuid4().hex}",
            "owner": worker_id,
            "claimed_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=lease_seconds)).isoformat(),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "controller": "native_continuation",
        "status": "ok",
        "operation": "claim",
        "todo_id": todo["id"],
        "claim": {
            "owner": worker_id,
            "status": "claimed",
            "lease": lease,
        },
        "decision": decision,
    }


def spend(state: dict[str, Any], *, slots: int) -> dict[str, Any]:
    if slots <= 0:
        raise ContractError("slots must be greater than zero")
    previous = _require_dict(state.get("previous_slice"), "previous_slice")
    if not _require_bool(previous.get("writeback_complete", False), "previous_slice.writeback_complete"):
        return {
            "schema_version": SCHEMA_VERSION,
            "controller": "native_continuation",
            "status": "invalid_transition",
            "operation": "spend",
            "reason_code": "writeback_incomplete",
            "reason": "quota cannot be spent before durable writeback",
        }
    if not _require_bool(previous.get("validated", False), "previous_slice.validated"):
        return {
            "schema_version": SCHEMA_VERSION,
            "controller": "native_continuation",
            "status": "invalid_transition",
            "operation": "spend",
            "reason_code": "slice_unvalidated",
            "reason": "quota cannot be spent before slice validation",
        }
    evidence_refs = _require_list(previous.get("evidence_refs", []), "previous_slice.evidence_refs")
    if not evidence_refs:
        return {
            "schema_version": SCHEMA_VERSION,
            "controller": "native_continuation",
            "status": "invalid_transition",
            "operation": "spend",
            "reason_code": "evidence_missing",
            "reason": "quota cannot be spent without evidence references",
        }

    quota = _quota_projection(state)
    projected_spent = quota["spent_slots"] + slots
    if projected_spent > quota["allowed_slots"]:
        return {
            "schema_version": SCHEMA_VERSION,
            "controller": "native_continuation",
            "status": "invalid_transition",
            "operation": "spend",
            "reason_code": "quota_overspend",
            "reason": f"spend would exceed quota: {projected_spent}/{quota['allowed_slots']}",
            "quota": quota,
        }

    projected = dict(quota)
    projected["spent_slots"] = projected_spent
    projected["eligible"] = projected_spent < projected["allowed_slots"]
    projected["state"] = "eligible" if projected["eligible"] else "throttled"
    projected["reason"] = f"quota spend accepted: {projected_spent}/{projected['allowed_slots']} slots spent"

    return {
        "schema_version": SCHEMA_VERSION,
        "controller": "native_continuation",
        "status": "ok",
        "operation": "spend",
        "spent_delta": slots,
        "evidence_refs": evidence_refs,
        "quota": projected,
    }


def _read_input(path_value: str) -> dict[str, Any]:
    if path_value == "-":
        text = sys.stdin.read()
    else:
        text = Path(path_value).read_text(encoding="utf-8")
    value = json.loads(text)
    return _require_dict(value, "input")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate native bounded continuation decisions for Unity Graph Engineering."
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)

    evaluate_parser = subparsers.add_parser("evaluate", help="Return the current should-run decision.")
    evaluate_parser.add_argument("--input", default="-", help="Input JSON path or '-' for stdin.")
    evaluate_parser.add_argument("--now", default=None, help="Deterministic ISO-8601 evaluation time.")

    claim_parser = subparsers.add_parser("claim", help="Project a claim/lease for the selected todo.")
    claim_parser.add_argument("--input", default="-", help="Input JSON path or '-' for stdin.")
    claim_parser.add_argument("--now", default=None, help="Deterministic ISO-8601 claim time.")
    claim_parser.add_argument("--lease-seconds", type=int, default=DEFAULT_LEASE_SECONDS)

    spend_parser = subparsers.add_parser("spend", help="Project quota spend after validated writeback.")
    spend_parser.add_argument("--input", default="-", help="Input JSON path or '-' for stdin.")
    spend_parser.add_argument("--slots", type=int, required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        state = _read_input(args.input)
        if args.operation == "evaluate":
            result = evaluate(state, now=_parse_time(args.now) if args.now else None)
        elif args.operation == "claim":
            result = claim(
                state,
                now=_parse_time(args.now) if args.now else None,
                lease_seconds=args.lease_seconds,
            )
        else:
            result = spend(state, slots=args.slots)
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        result = {
            "schema_version": SCHEMA_VERSION,
            "controller": "native_continuation",
            "status": "invalid_request",
            "reason": str(exc),
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "ok":
        return 0
    if result["status"] == "invalid_request":
        return 4
    return 3


if __name__ == "__main__":
    sys.exit(main())
