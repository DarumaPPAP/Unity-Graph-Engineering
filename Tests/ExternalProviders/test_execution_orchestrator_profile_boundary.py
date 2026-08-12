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
spec = importlib.util.spec_from_file_location("execution_orchestrator_profile_boundary", MODULE_PATH)
orchestrator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(orchestrator)


class ExecutionOrchestratorProfileBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        (self.workspace / "source.cs").write_text("class A {}", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def state(self, profile: str) -> dict:
        return {
            "execution_mode": "graph_loop",
            "execution_profile": profile,
            "goal_id": "goal-1",
            "goal_complete": False,
            "health": {"ok": True},
            "human_gate": {"required": False, "satisfied": True},
            "evidence_wait": {"waiting": False},
            "focus_wait": {"waiting": False},
            "budget": {"remaining": True},
            "quota": {"compute_share": 1.0, "allowed_slots": 10, "spent_slots": 0},
            "worker": {"id": "worker-1", "multiple_workers": False},
            "available_capabilities": [],
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

    def decision(self) -> dict:
        return {
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

    def request(self, profile: str, work_kind: str, source: dict) -> dict:
        return {
            "execution_profile": profile,
            "execution_state": self.state(profile),
            "work_kind": work_kind,
            "source_verification": source,
            "memory": {"enabled": False},
            "code_intelligence": {"enabled": False},
        }

    @mock.patch.object(orchestrator, "_continuation")
    def test_generic_mutation_is_blocked_before_continuation(self, continuation):
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(
                self.workspace,
                self.request(
                    "generic_planning",
                    "mutation",
                    {
                        "completed": True,
                        "scope_class": "portable_artifact",
                        "paths": [],
                        "evidence_refs": ["ev-1"],
                    },
                ),
            )
        self.assertEqual(caught.exception.code, "work_kind_profile_forbidden")
        continuation.assert_not_called()

    @mock.patch.object(orchestrator, "_continuation")
    def test_team_safe_general_mutation_is_blocked_before_continuation(self, continuation):
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(
                self.workspace,
                self.request(
                    "team_safe_import",
                    "mutation",
                    {
                        "completed": True,
                        "scope_class": "portable_artifact",
                        "paths": [],
                        "evidence_refs": ["ev-1"],
                    },
                ),
            )
        self.assertEqual(caught.exception.code, "work_kind_profile_forbidden")
        continuation.assert_not_called()

    @mock.patch.object(orchestrator, "_continuation")
    def test_team_safe_portable_import_is_evidence_only_and_can_prepare(self, continuation):
        continuation.return_value = self.decision()
        result = orchestrator.prepare(
            self.workspace,
            self.request(
                "team_safe_import",
                "portable_import",
                {
                    "completed": True,
                    "scope_class": "portable_artifact",
                    "paths": [],
                    "evidence_refs": ["portable-package-verification-1"],
                },
            ),
        )
        self.assertTrue(result["ready_for_execution"])
        self.assertEqual(result["ticket"]["work_kind"], "portable_import")
        self.assertEqual(result["ticket"]["source_verification"]["paths"], [])
        self.assertEqual(
            result["ticket"]["source_verification"]["evidence_refs"],
            ["portable-package-verification-1"],
        )

    @mock.patch.object(orchestrator, "_continuation")
    def test_team_safe_portable_import_local_path_is_forbidden(self, continuation):
        continuation.return_value = self.decision()
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(
                self.workspace,
                self.request(
                    "team_safe_import",
                    "portable_import",
                    {
                        "completed": True,
                        "scope_class": "portable_artifact",
                        "paths": ["source.cs"],
                        "evidence_refs": ["ev-1"],
                    },
                ),
            )
        self.assertEqual(caught.exception.code, "non_personal_source_path_forbidden")

    @mock.patch.object(orchestrator, "_continuation")
    def test_personal_cannot_use_portable_import_work_kind(self, continuation):
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(
                self.workspace,
                self.request(
                    "personal_full_control",
                    "portable_import",
                    {
                        "completed": True,
                        "scope_class": "portable_artifact",
                        "paths": ["source.cs"],
                        "evidence_refs": ["ev-1"],
                    },
                ),
            )
        self.assertEqual(caught.exception.code, "work_kind_profile_forbidden")
        continuation.assert_not_called()

    @mock.patch.object(orchestrator, "_continuation")
    def test_generic_verification_cannot_open_local_source_path(self, continuation):
        continuation.return_value = self.decision()
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(
                self.workspace,
                self.request(
                    "generic_planning",
                    "verification",
                    {
                        "completed": True,
                        "scope_class": "public_reference",
                        "paths": ["source.cs"],
                        "evidence_refs": ["ev-1"],
                    },
                ),
            )
        self.assertEqual(caught.exception.code, "non_personal_source_path_forbidden")


if __name__ == "__main__":
    unittest.main()
