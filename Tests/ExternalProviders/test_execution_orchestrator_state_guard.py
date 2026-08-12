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
spec = importlib.util.spec_from_file_location("execution_orchestrator_state_guard", MODULE_PATH)
orchestrator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(orchestrator)


class ExecutionOrchestratorStateGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def valid_state(self):
        return {
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
            "available_capabilities": [],
            "todos": [],
            "todos_truncated": False,
        }

    @mock.patch.object(orchestrator, "_continuation")
    def test_missing_human_gate_fails_before_continuation(self, continuation):
        state = self.valid_state()
        del state["human_gate"]
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(
                self.workspace,
                {
                    "execution_profile": "personal_full_control",
                    "execution_state": state,
                    "work_kind": "analysis",
                    "source_verification": {"completed": False, "paths": [], "evidence_refs": []},
                    "memory": {"enabled": False},
                    "code_intelligence": {"enabled": False},
                },
            )
        self.assertIn(caught.exception.code, {"invalid_request", "incomplete_control_state"})
        continuation.assert_not_called()

    @mock.patch.object(orchestrator, "_continuation")
    def test_missing_budget_remaining_fails_before_continuation(self, continuation):
        state = self.valid_state()
        state["budget"] = {}
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator.prepare(
                self.workspace,
                {
                    "execution_profile": "personal_full_control",
                    "execution_state": state,
                    "work_kind": "analysis",
                    "source_verification": {"completed": False, "paths": [], "evidence_refs": []},
                    "memory": {"enabled": False},
                    "code_intelligence": {"enabled": False},
                },
            )
        self.assertEqual(caught.exception.code, "incomplete_control_state")
        continuation.assert_not_called()

    def test_missing_quota_values_fail_closed(self):
        state = self.valid_state()
        del state["quota"]["allowed_slots"]
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator._validate_control_state(state, "personal_full_control")
        self.assertEqual(caught.exception.code, "incomplete_control_state")

    def test_profile_mismatch_fails_closed(self):
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator._validate_control_state(self.valid_state(), "team_safe_import")
        self.assertEqual(caught.exception.code, "profile_mismatch")


if __name__ == "__main__":
    unittest.main()
