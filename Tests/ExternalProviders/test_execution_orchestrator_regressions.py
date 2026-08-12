from __future__ import annotations

import importlib.util
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
spec = importlib.util.spec_from_file_location("execution_orchestrator_regression", MODULE_PATH)
orchestrator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(orchestrator)


class ExecutionOrchestratorRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        (self.workspace / "src.cs").write_text("class A {}", encoding="utf-8")
        (self.workspace / "evidence.txt").write_text("validated result", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def state(self):
        return {
            "run_id": "run-1",
            "execution_mode": "graph_loop",
            "execution_profile": "personal_full_control",
            "goal_id": "goal-1",
            "goal_complete": False,
            "health": {"ok": True},
            "human_gate": {"required": False, "satisfied": True},
            "evidence_wait": {"waiting": False},
            "focus_wait": {"waiting": False},
            "budget": {"remaining": True},
            "quota": {"compute_share": 1.0, "allowed_slots": 10, "spent_slots": 0},
            "worker": {"id": "worker-1", "multiple_workers": False},
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

    def decision(self, selected=True):
        return {
            "schema_version": "1.0",
            "controller": "native_continuation",
            "status": "ok",
            "decision": "run",
            "should_run": True,
            "lane": "bounded_work",
            "reason_code": "advancement_todo_runnable" if selected else "hidden_todo_conservative_advance",
            "reason": "run",
            "effective_action": "run_bounded_slice" if selected else "materialize_advancement_todo_or_blocker",
            "must_attempt_work": True,
            "normal_delivery_allowed": selected,
            "selected_todo": (
                {
                    "id": "todo-1",
                    "status": "unclaimed",
                    "task_class": "advancement_task",
                    "required_capabilities": [],
                }
                if selected
                else None
            ),
            "runnable_candidates": [],
            "blocked_candidates": [],
            "capability_gate": None,
            "quota": {"compute_share": 1.0, "allowed_slots": 10, "spent_slots": 0},
            "diagnostics": [],
        }

    @mock.patch.object(orchestrator, "_continuation")
    def test_prepare_without_selected_todo_never_issues_ticket_or_navigation(self, continuation):
        continuation.return_value = self.decision(selected=False)
        request = {
            "execution_profile": "personal_full_control",
            "execution_state": self.state(),
            "work_kind": "analysis",
            "source_verification": {"completed": False, "paths": [], "evidence_refs": []},
            "memory": {"enabled": True, "query": "renderer"},
            "code_intelligence": {"enabled": True, "operation": "impact", "target": "A"},
        }
        with mock.patch.object(orchestrator, "_memory") as memory, mock.patch.object(orchestrator, "_ix") as ix:
            result = orchestrator.prepare(self.workspace, request)
        self.assertFalse(result["ready_for_execution"])
        self.assertIsNone(result["ticket"])
        self.assertEqual(result["required_next_action"], "materialize_advancement_todo_or_blocker")
        memory.assert_not_called()
        ix.assert_not_called()

    @mock.patch.object(orchestrator, "_continuation")
    def test_mutation_source_verification_requires_evidence_reference(self, continuation):
        continuation.return_value = self.decision(selected=True)
        request = {
            "execution_profile": "personal_full_control",
            "execution_state": self.state(),
            "work_kind": "mutation",
            "source_verification": {
                "completed": True,
                "scope_class": "project_internal",
                "paths": ["src.cs"],
                "evidence_refs": [],
            },
            "memory": {"enabled": False},
            "code_intelligence": {"enabled": False},
        }
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(self.workspace, request)
        self.assertEqual(caught.exception.code, "source_verification_evidence_missing")

    @mock.patch.object(orchestrator, "_continuation")
    @mock.patch.object(orchestrator, "_memory")
    def test_stale_ticket_preserves_evidence_but_never_spends_quota(self, memory, continuation):
        original = self.state()
        ticket = orchestrator._ticket(
            profile="personal_full_control",
            work_kind="mutation",
            state=original,
            decision=self.decision(selected=True),
            source_verification={
                "completed": True,
                "required": True,
                "scope_class": "project_internal",
                "paths": ["src.cs"],
                "evidence_refs": ["source-read-1"],
            },
        )
        changed = self.state()
        changed["quota"]["spent_slots"] = 1
        memory.return_value = {
            "schema_version": "1.1",
            "controller": "layered_memory",
            "operation": "capture_raw",
            "status": "ok",
            "mutated": True,
            "data": {"memory_id": "ev-stale"},
            "diagnostics": [],
        }
        request = {
            "execution_profile": "personal_full_control",
            "execution_state": changed,
            "ticket": ticket,
            "slice_result": {
                "slice_id": "slice-1",
                "todo_id": "todo-1",
                "completed_at": "2026-08-12T04:00:00+00:00",
                "writeback_complete": True,
                "validated": True,
                "evidence_id": "ev-stale",
                "evidence_file": "evidence.txt",
                "scope_class": "project_internal",
                "atom": {"enabled": False},
            },
        }
        result = orchestrator.finalize(self.workspace, request)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["required_next_action"], "reprepare_from_authoritative_state")
        self.assertTrue(any(d["code"] == "stale_execution_state" for d in result["diagnostics"]))
        continuation.assert_not_called()
        memory.assert_called_once()

    @mock.patch.object(orchestrator, "_continuation")
    def test_prepare_ticket_uses_workspace_relative_source_paths(self, continuation):
        continuation.return_value = self.decision(selected=True)
        result = orchestrator.prepare(
            self.workspace,
            {
                "execution_profile": "personal_full_control",
                "execution_state": self.state(),
                "work_kind": "mutation",
                "source_verification": {
                    "completed": True,
                    "scope_class": "project_internal",
                    "paths": [str((self.workspace / "src.cs").resolve())],
                    "evidence_refs": ["source-read-1"],
                },
                "memory": {"enabled": False},
                "code_intelligence": {"enabled": False},
            },
        )
        self.assertEqual(result["ticket"]["source_verification"]["paths"], ["src.cs"])


if __name__ == "__main__":
    unittest.main()
