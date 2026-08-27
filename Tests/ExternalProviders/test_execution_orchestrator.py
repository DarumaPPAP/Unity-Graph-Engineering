from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "Tools"
    / "ExecutionOrchestrator"
    / "execution_orchestrator.py"
)
spec = importlib.util.spec_from_file_location("execution_orchestrator", MODULE_PATH)
orchestrator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(orchestrator)


class ExecutionOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        (self.workspace / "src.cs").write_text("class A {}", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def state(self, profile="personal_full_control", multiple_workers=False):
        return {
            "run_id": "run-1",
            "execution_mode": "graph_loop",
            "execution_profile": profile,
            "goal_id": "goal-1",
            "goal_complete": False,
            "health": {"ok": True},
            "human_gate": {"required": False, "satisfied": True},
            "evidence_wait": {"waiting": False},
            "focus_wait": {"waiting": False},
            "budget": {"remaining": True},
            "quota": {
                "compute_share": 1.0,
                "window_hours": 24,
                "slot_minutes": 1,
                "allowed_slots": 10,
                "spent_slots": 0,
            },
            "worker": {"id": "worker-1", "multiple_workers": multiple_workers},
            "available_capabilities": ["shell", "filesystem_read", "filesystem_write"],
            "todos": [
                {
                    "id": "todo-1",
                    "status": "unclaimed",
                    "task_class": "advancement_task",
                    "required_capabilities": [],
                }
            ],
            "todos_truncated": False,
        }

    def decision(self, **overrides):
        value = {
            "schema_version": "1.0",
            "controller": "native_continuation",
            "status": "ok",
            "decision": "run",
            "should_run": True,
            "lane": "bounded_work",
            "reason_code": "advancement_todo_runnable",
            "reason": "runnable",
            "effective_action": "run_bounded_slice",
            "must_attempt_work": True,
            "normal_delivery_allowed": True,
            "selected_todo": {
                "id": "todo-1",
                "status": "unclaimed",
                "task_class": "advancement_task",
                "required_capabilities": [],
            },
            "runnable_candidates": [{"todo_id": "todo-1"}],
            "blocked_candidates": [],
            "capability_gate": {"action": "run"},
            "quota": {"compute_share": 1.0, "allowed_slots": 10, "spent_slots": 0},
            "diagnostics": [],
        }
        value.update(overrides)
        return value

    def prepare_request(self, profile="personal_full_control", work_kind="mutation", **overrides):
        request = {
            "execution_profile": profile,
            "execution_state": self.state(profile=profile),
            "work_kind": work_kind,
            "source_verification": {
                "completed": True,
                "scope_class": "project_internal" if profile == "personal_full_control" else "portable_artifact",
                "paths": ["src.cs"],
                "evidence_refs": ["source-read-1"],
            },
            "memory": {"enabled": False},
            "code_intelligence": {"enabled": False},
        }
        request.update(overrides)
        return request

    def ticket(self, state=None, profile="personal_full_control", work_kind=None):
        state = state or self.state(profile=profile)
        effective_work_kind = work_kind or (
            "portable_import" if profile == "team_safe_import" else "mutation"
        )
        source = {
            "completed": True,
            "required": True,
            "scope_class": "project_internal" if profile == "personal_full_control" else "portable_artifact",
            "paths": (
                [str((self.workspace / "src.cs").resolve())]
                if profile == "personal_full_control"
                else []
            ),
            "evidence_refs": ["source-read-1"],
        }
        return orchestrator._ticket(
            profile=profile,
            work_kind=effective_work_kind,
            state=state,
            decision=self.decision(),
            source_verification=source,
        )

    def finalize_request(self, profile="personal_full_control", state=None, atom=False):
        state = state or self.state(profile=profile)
        evidence = self.workspace / "evidence.txt"
        evidence.write_text("tests passed", encoding="utf-8")
        result = {
            "slice_id": "slice-1",
            "todo_id": "todo-1",
            "completed_at": "2026-08-12T04:00:00+00:00",
            "writeback_complete": True,
            "validated": True,
            "evidence_id": "ev-slice-1",
            "evidence_file": "evidence.txt",
            "scope_class": "project_internal" if profile == "personal_full_control" else "portable_artifact",
            "source_type": "test_result",
            "summary": "tests passed",
            "slots": 1,
            "atom": {"enabled": atom},
        }
        if atom:
            result["atom"] = {
                "enabled": True,
                "memory_id": "atom-slice-1",
                "statement": "Slice tests passed",
                "confidence": "verified",
            }
        return {
            "execution_profile": profile,
            "execution_state": state,
            "ticket": self.ticket(state=state, profile=profile),
            "slice_result": result,
        }

    @mock.patch.object(orchestrator, "_continuation")
    def test_human_gate_short_circuits_before_other_controllers(self, continuation):
        continuation.return_value = self.decision(
            decision="ask_human",
            should_run=False,
            lane="human_gate",
            effective_action="request_human_decision",
            selected_todo=None,
        )
        with mock.patch.object(orchestrator, "_memory") as memory, mock.patch.object(orchestrator, "_ix") as ix:
            result = orchestrator.prepare(self.workspace, self.prepare_request())
        self.assertFalse(result["ready_for_execution"])
        memory.assert_not_called()
        ix.assert_not_called()

    @mock.patch.object(orchestrator, "_continuation")
    def test_quota_pause_short_circuits(self, continuation):
        continuation.return_value = self.decision(
            decision="wait",
            should_run=False,
            lane="compute_quota",
            effective_action="quota_pause",
            selected_todo=None,
        )
        result = orchestrator.prepare(self.workspace, self.prepare_request())
        self.assertEqual(result["required_next_action"], "quota_pause")

    @mock.patch.object(orchestrator, "_continuation")
    def test_mutation_requires_direct_source_read(self, continuation):
        continuation.return_value = self.decision()
        request = self.prepare_request()
        request["source_verification"] = {"completed": False, "paths": [], "evidence_refs": []}
        result = orchestrator.prepare(self.workspace, request)
        self.assertFalse(result["ready_for_execution"])
        self.assertEqual(result["required_next_action"], "direct_source_read")

    @mock.patch.object(orchestrator, "_continuation")
    def test_analysis_can_prepare_without_source_read(self, continuation):
        continuation.return_value = self.decision()
        request = self.prepare_request(work_kind="analysis")
        request["source_verification"] = {"completed": False, "paths": [], "evidence_refs": []}
        result = orchestrator.prepare(self.workspace, request)
        self.assertTrue(result["ready_for_execution"])
        self.assertIsNotNone(result["ticket"])

    @mock.patch.object(orchestrator, "_continuation")
    def test_source_verification_path_escape_is_blocked(self, continuation):
        continuation.return_value = self.decision()
        request = self.prepare_request()
        request["source_verification"]["paths"] = ["../outside.cs"]
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(self.workspace, request)
        self.assertEqual(caught.exception.code, "path_escape_forbidden")

    @mock.patch.object(orchestrator, "_continuation")
    def test_non_personal_internal_source_scope_is_blocked(self, continuation):
        continuation.return_value = self.decision()
        request = self.prepare_request(profile="team_safe_import")
        request["source_verification"]["scope_class"] = "project_internal"
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(self.workspace, request)
        self.assertEqual(caught.exception.code, "source_scope_forbidden")

    @mock.patch.object(orchestrator, "_continuation")
    def test_multiple_worker_requires_durable_claim_before_navigation(self, continuation):
        state = self.state(multiple_workers=True)
        request = self.prepare_request()
        request["execution_state"] = state
        continuation.side_effect = [
            self.decision(),
            {
                "schema_version": "1.0",
                "controller": "native_continuation",
                "status": "ok",
                "operation": "claim",
                "todo_id": "todo-1",
                "claim": {
                    "owner": "worker-1",
                    "status": "claimed",
                    "lease": {"id": "lease-new", "owner": "worker-1"},
                },
                "decision": self.decision(),
            },
        ]
        with mock.patch.object(orchestrator, "_memory") as memory, mock.patch.object(orchestrator, "_ix") as ix:
            result = orchestrator.prepare(self.workspace, request)
        self.assertFalse(result["ready_for_execution"])
        self.assertEqual(result["required_next_action"], "write_claim_to_authoritative_state")
        memory.assert_not_called()
        ix.assert_not_called()

    @mock.patch.object(orchestrator, "_continuation")
    def test_existing_self_lease_allows_prepare(self, continuation):
        state = self.state(multiple_workers=True)
        state["todos"][0]["lease"] = {"id": "lease-1", "owner": "worker-1"}
        decision = self.decision()
        decision["selected_todo"]["lease"] = {"id": "lease-1", "owner": "worker-1"}
        continuation.side_effect = [
            decision,
            {
                "schema_version": "1.0",
                "controller": "native_continuation",
                "status": "ok",
                "operation": "claim",
                "todo_id": "todo-1",
                "claim": {
                    "owner": "worker-1",
                    "status": "claimed",
                    "lease": {"id": "lease-1", "owner": "worker-1"},
                },
                "decision": decision,
            },
        ]
        request = self.prepare_request()
        request["execution_state"] = state
        result = orchestrator.prepare(self.workspace, request)
        self.assertTrue(result["ready_for_execution"])

    @mock.patch.object(orchestrator, "_continuation")
    @mock.patch.object(orchestrator, "_ix")
    def test_team_safe_never_invokes_ix(self, ix, continuation):
        continuation.return_value = self.decision()
        request = self.prepare_request(profile="team_safe_import", work_kind="analysis")
        request["source_verification"] = {"completed": False, "paths": [], "evidence_refs": []}
        request["code_intelligence"] = {"enabled": True, "operation": "impact", "target": "Foo"}
        result = orchestrator.prepare(self.workspace, request)
        ix.assert_not_called()
        self.assertTrue(any(d["code"] == "ix_prohibited_for_profile" for d in result["diagnostics"]))

    @mock.patch.object(orchestrator, "_continuation")
    @mock.patch.object(orchestrator, "_ix")
    def test_generic_never_invokes_ix(self, ix, continuation):
        continuation.return_value = self.decision()
        request = self.prepare_request(profile="generic_planning", work_kind="analysis")
        request["source_verification"] = {"completed": False, "paths": [], "evidence_refs": []}
        request["code_intelligence"] = {"enabled": True, "operation": "trace", "target": "Foo"}
        orchestrator.prepare(self.workspace, request)
        ix.assert_not_called()

    @mock.patch.object(orchestrator, "_continuation")
    @mock.patch.object(orchestrator, "_ix")
    def test_ix_unavailable_falls_back_without_blocking(self, ix, continuation):
        continuation.return_value = self.decision()
        ix.return_value = {
            "provider": "ix",
            "status": "unavailable",
            "available": False,
            "fallback": "targeted_source_read",
        }
        request = self.prepare_request(work_kind="analysis")
        request["source_verification"] = {"completed": False, "paths": [], "evidence_refs": []}
        request["code_intelligence"] = {"enabled": True, "operation": "impact", "target": "Foo"}
        result = orchestrator.prepare(self.workspace, request)
        self.assertTrue(result["ready_for_execution"])
        self.assertTrue(any(d["code"] == "ix_fallback" for d in result["diagnostics"]))

    @mock.patch.object(orchestrator, "_continuation")
    @mock.patch.object(orchestrator, "_memory")
    def test_empty_memory_query_is_not_broad_loaded(self, memory, continuation):
        continuation.return_value = self.decision()
        request = self.prepare_request(work_kind="analysis")
        request["source_verification"] = {"completed": False, "paths": [], "evidence_refs": []}
        request["memory"] = {"enabled": True, "query": ""}
        result = orchestrator.prepare(self.workspace, request)
        memory.assert_not_called()
        self.assertTrue(any(d["code"] == "memory_query_empty" for d in result["diagnostics"]))

    @mock.patch.object(orchestrator, "_continuation")
    @mock.patch.object(orchestrator, "_memory")
    def test_memory_failure_degrades_without_blocking(self, memory, continuation):
        continuation.return_value = self.decision()
        memory.return_value = {"controller": "layered_memory", "status": "blocked"}
        request = self.prepare_request(work_kind="analysis")
        request["source_verification"] = {"completed": False, "paths": [], "evidence_refs": []}
        request["memory"] = {"enabled": True, "query": "renderer"}
        result = orchestrator.prepare(self.workspace, request)
        self.assertTrue(result["ready_for_execution"])
        self.assertIsNone(result["memory"])

    @mock.patch.object(orchestrator, "_continuation")
    @mock.patch.object(orchestrator, "_memory")
    def test_memory_raw_content_contract_breach_blocks(self, memory, continuation):
        continuation.return_value = self.decision()
        memory.return_value = {
            "controller": "layered_memory",
            "status": "ok",
            "data": {"raw_content_included": True, "items": []},
        }
        request = self.prepare_request(work_kind="analysis")
        request["source_verification"] = {"completed": False, "paths": [], "evidence_refs": []}
        request["memory"] = {"enabled": True, "query": "renderer"}
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(self.workspace, request)
        self.assertEqual(caught.exception.code, "memory_contract_breach")

    @mock.patch.object(orchestrator, "_continuation")
    @mock.patch.object(orchestrator, "_memory")
    def test_defense_in_depth_blocks_nonpersonal_memory_scope_leak(self, memory, continuation):
        continuation.return_value = self.decision()
        memory.return_value = {
            "controller": "layered_memory",
            "status": "ok",
            "data": {
                "raw_content_included": False,
                "items": [{"memory_id": "secret", "scope_class": "project_internal"}],
            },
        }
        request = self.prepare_request(profile="team_safe_import", work_kind="analysis")
        request["source_verification"] = {"completed": False, "paths": [], "evidence_refs": []}
        request["memory"] = {"enabled": True, "query": "renderer"}
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(self.workspace, request)
        self.assertEqual(caught.exception.code, "memory_scope_leak")

    @mock.patch.object(orchestrator, "_continuation")
    def test_ticket_is_deterministic_for_same_state(self, continuation):
        continuation.return_value = self.decision()
        request = self.prepare_request()
        first = orchestrator.prepare(self.workspace, request)
        second = orchestrator.prepare(self.workspace, request)
        self.assertEqual(first["ticket"]["ticket_id"], second["ticket"]["ticket_id"])
        self.assertEqual(first["ticket"]["ticket_digest"], second["ticket"]["ticket_digest"])

    def test_ticket_tampering_is_detected(self):
        ticket = self.ticket()
        ticket["selected_todo_id"] = "other"
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator._verify_ticket(ticket)
        self.assertEqual(caught.exception.code, "ticket_integrity_failed")

    def test_finalize_rejects_evidence_path_escape(self):
        request = self.finalize_request()
        request["slice_result"]["evidence_file"] = "../outside.txt"
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.finalize(self.workspace, request)
        self.assertEqual(caught.exception.code, "path_escape_forbidden")

    def test_finalize_requires_validated_writeback(self):
        request = self.finalize_request()
        request["slice_result"]["validated"] = False
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.finalize(self.workspace, request)
        self.assertEqual(caught.exception.code, "slice_unvalidated")

    def test_finalize_rejects_todo_mismatch(self):
        request = self.finalize_request()
        request["slice_result"]["todo_id"] = "todo-other"
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.finalize(self.workspace, request)
        self.assertEqual(caught.exception.code, "ticket_todo_mismatch")

    @mock.patch.object(orchestrator, "_memory")
    @mock.patch.object(orchestrator, "_continuation")
    def test_finalize_orders_evidence_before_quota_spend(self, continuation, memory):
        calls = []

        def mem_side(workspace, payload):
            calls.append(payload["operation"])
            return {
                "controller": "layered_memory",
                "status": "ok",
                "operation": payload["operation"],
                "data": {"memory_id": payload.get("evidence_id")},
                "mutated": True,
            }

        def cont_side(operation, state, **kwargs):
            calls.append(operation)
            return {
                "controller": "native_continuation",
                "status": "ok",
                "operation": "spend",
                "quota": {"spent_slots": 1},
            }

        memory.side_effect = mem_side
        continuation.side_effect = cont_side
        result = orchestrator.finalize(self.workspace, self.finalize_request())
        self.assertEqual(calls, ["capture_raw", "spend"])
        self.assertEqual(result["required_state_writeback"]["quota"]["spent_slots"], 1)

    @mock.patch.object(orchestrator, "_memory")
    @mock.patch.object(orchestrator, "_continuation")
    def test_finalize_optional_atom_is_before_spend(self, continuation, memory):
        calls = []
        memory.side_effect = lambda workspace, payload: (
            calls.append(payload["operation"])
            or {
                "controller": "layered_memory",
                "status": "ok",
                "operation": payload["operation"],
                "data": {},
                "mutated": True,
            }
        )
        continuation.side_effect = lambda operation, state, **kwargs: (
            calls.append(operation)
            or {
                "controller": "native_continuation",
                "status": "ok",
                "operation": "spend",
                "quota": {"spent_slots": 1},
            }
        )
        orchestrator.finalize(self.workspace, self.finalize_request(atom=True))
        self.assertEqual(calls, ["capture_raw", "create_atom", "spend"])

    @mock.patch.object(orchestrator, "_memory")
    @mock.patch.object(orchestrator, "_continuation")
    def test_memory_capture_failure_prevents_spend(self, continuation, memory):
        memory.return_value = {"controller": "layered_memory", "status": "blocked"}
        result = orchestrator.finalize(self.workspace, self.finalize_request())
        self.assertEqual(result["status"], "blocked")
        continuation.assert_not_called()

    @mock.patch.object(orchestrator, "_memory")
    @mock.patch.object(orchestrator, "_continuation")
    def test_quota_failure_preserves_evidence_without_state_patch(self, continuation, memory):
        memory.return_value = {
            "controller": "layered_memory",
            "status": "ok",
            "operation": "capture_raw",
            "data": {},
            "mutated": True,
        }
        continuation.return_value = {
            "controller": "native_continuation",
            "status": "invalid_transition",
            "operation": "spend",
            "reason_code": "quota_overspend",
        }
        result = orchestrator.finalize(self.workspace, self.finalize_request())
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["required_state_writeback"])
        self.assertTrue(
            any(d["code"] == "evidence_preserved_without_quota_spend" for d in result["diagnostics"])
        )

    @mock.patch.object(orchestrator, "_memory")
    @mock.patch.object(orchestrator, "_continuation")
    def test_finalize_writeback_marks_quota_spent(self, continuation, memory):
        memory.return_value = {
            "controller": "layered_memory",
            "status": "ok",
            "operation": "capture_raw",
            "data": {},
            "mutated": True,
        }
        continuation.return_value = {
            "controller": "native_continuation",
            "status": "ok",
            "operation": "spend",
            "quota": {"spent_slots": 1},
        }
        result = orchestrator.finalize(self.workspace, self.finalize_request())
        previous = result["required_state_writeback"]["previous_slice"]
        self.assertTrue(previous["quota_spent"])
        self.assertTrue(previous["orchestrated"])
        self.assertTrue(previous["quota_spend_id"].startswith("spend-"))

    @mock.patch.object(orchestrator, "_memory")
    @mock.patch.object(orchestrator, "_continuation")
    def test_finalize_is_idempotent_after_quota_spent(self, continuation, memory):
        state = self.state()
        state["previous_slice"] = {
            "slice_id": "slice-1",
            "quota_spent": True,
            "writeback_complete": True,
            "validated": True,
            "evidence_refs": ["ev-slice-1"],
        }
        memory.return_value = {
            "controller": "layered_memory",
            "status": "ok",
            "operation": "capture_raw",
            "data": {},
            "mutated": False,
        }
        request = self.finalize_request(state=state)
        result = orchestrator.finalize(self.workspace, request)
        self.assertEqual(result["quota"]["spent_delta"], 0)
        self.assertTrue(result["quota"]["idempotent_replay"])
        continuation.assert_not_called()

    def test_finalize_nonpersonal_internal_evidence_scope_is_blocked(self):
        request = self.finalize_request(profile="team_safe_import")
        request["slice_result"]["scope_class"] = "project_internal"
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.finalize(self.workspace, request)
        self.assertEqual(caught.exception.code, "evidence_scope_forbidden")

    @mock.patch("subprocess.run")
    def test_controller_subprocess_never_uses_shell(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["python"],
            returncode=0,
            stdout=json.dumps({"controller": "native_continuation", "status": "ok"}),
            stderr="",
        )
        orchestrator._run_json(
            [sys.executable, "fake.py"],
            {"x": 1},
            timeout=1,
            expected_identity=("controller", "native_continuation"),
        )
        self.assertFalse(run.call_args.kwargs["shell"])

    @mock.patch("subprocess.run")
    def test_non_json_controller_output_is_blocked(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["python"],
            returncode=0,
            stdout="oops",
            stderr="",
        )
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator._run_json([sys.executable, "fake.py"], {}, timeout=1)
        self.assertEqual(caught.exception.code, "controller_non_json")

    @mock.patch("subprocess.run")
    def test_wrong_controller_identity_is_blocked(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["python"],
            returncode=0,
            stdout=json.dumps({"controller": "wrong", "status": "ok"}),
            stderr="",
        )
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator._run_json(
                [sys.executable, "fake.py"],
                {},
                timeout=1,
                expected_identity=("controller", "native_continuation"),
            )
        self.assertEqual(caught.exception.code, "controller_identity_mismatch")

    @mock.patch("subprocess.run")
    def test_controller_timeout_is_blocked(self, run):
        run.side_effect = subprocess.TimeoutExpired(cmd="fake", timeout=1)
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator._run_json([sys.executable, "fake.py"], {}, timeout=1)
        self.assertEqual(caught.exception.code, "controller_timeout")

    def test_envelope_explicitly_denies_authority_ownership(self):
        result = orchestrator._envelope("prepare", "ok", ready=False)
        self.assertFalse(result["authority"]["owns_source_mutation"])
        self.assertFalse(result["authority"]["owns_state_current"])
        self.assertFalse(result["authority"]["owns_human_gate"])


if __name__ == "__main__":
    unittest.main()
