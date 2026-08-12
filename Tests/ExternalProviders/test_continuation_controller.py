#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[2] / "Tools" / "ContinuationController" / "continuation_controller.py"
SPEC = importlib.util.spec_from_file_location("continuation_controller", MODULE_PATH)
controller = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(controller)

NOW = datetime(2026, 8, 12, 4, 0, tzinfo=timezone.utc)


def base_state():
    return {
        "schema_version": "1.0",
        "goal_id": "goal-a",
        "execution_mode": "graph_loop",
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
            "spent_slots": 0,
        },
        "worker": {"id": "worker-a", "multiple_workers": True},
        "available_capabilities": ["shell", "filesystem_read", "filesystem_write"],
        "previous_slice": None,
        "todos_truncated": False,
        "todos": [
            {
                "id": "todo-a",
                "status": "unclaimed",
                "task_class": "advancement_task",
                "required_capabilities": ["shell"],
            }
        ],
    }


class ContinuationControllerTests(unittest.TestCase):
    def test_human_gate_precedes_quota(self):
        state = base_state()
        state["human_gate"] = {"required": True, "satisfied": False, "reason": "merge approval"}
        state["quota"]["compute_share"] = 1.0
        result = controller.evaluate(state, now=NOW)
        self.assertEqual("ask_human", result["decision"])
        self.assertFalse(result["should_run"])
        self.assertEqual("human_gate", result["lane"])

    def test_health_gate_precedes_everything(self):
        state = base_state()
        state["health"] = {"ok": False, "reason": "contract broken"}
        result = controller.evaluate(state, now=NOW)
        self.assertEqual("blocked", result["decision"])
        self.assertEqual("health_blocked", result["reason_code"])

    def test_writeback_must_complete_before_next_slice(self):
        state = base_state()
        state["previous_slice"] = {
            "writeback_complete": False,
            "validated": True,
            "evidence_refs": ["e-1"],
        }
        result = controller.evaluate(state, now=NOW)
        self.assertEqual("blocked", result["decision"])
        self.assertEqual("writeback_incomplete", result["reason_code"])

    def test_quota_zero_pauses_goal_without_completion(self):
        state = base_state()
        state["quota"]["compute_share"] = 0.0
        result = controller.evaluate(state, now=NOW)
        self.assertEqual("wait", result["decision"])
        self.assertEqual("quota_paused", result["reason_code"])
        self.assertFalse(result["should_run"])

    def test_quota_exhausted_is_throttled(self):
        state = base_state()
        state["quota"]["compute_share"] = 0.5
        state["quota"]["spent_slots"] = 720
        result = controller.evaluate(state, now=NOW)
        self.assertEqual("quota_exhausted", result["reason_code"])
        self.assertEqual(720, result["quota"]["allowed_slots"])

    def test_runnable_advancement_todo_runs(self):
        result = controller.evaluate(base_state(), now=NOW)
        self.assertEqual("run", result["decision"])
        self.assertTrue(result["should_run"])
        self.assertEqual("todo-a", result["selected_todo"]["id"])
        self.assertTrue(result["normal_delivery_allowed"])

    def test_monitor_only_lane_is_quiet(self):
        state = base_state()
        state["todos"][0]["task_class"] = "continuous_monitor"
        result = controller.evaluate(state, now=NOW)
        self.assertEqual("wait", result["decision"])
        self.assertEqual("monitor_quiet", result["reason_code"])
        self.assertEqual("monitor_quiet_skip", result["effective_action"])

    def test_hidden_todos_force_conservative_advancement(self):
        state = base_state()
        state["todos"] = []
        state["todos_truncated"] = True
        result = controller.evaluate(state, now=NOW)
        self.assertEqual("run", result["decision"])
        self.assertTrue(result["should_run"])
        self.assertFalse(result["normal_delivery_allowed"])
        self.assertEqual("materialize_advancement_todo_or_blocker", result["effective_action"])

    def test_owner_held_capability_asks_human(self):
        state = base_state()
        state["todos"][0]["required_capabilities"] = ["credentials"]
        result = controller.evaluate(state, now=NOW)
        self.assertEqual("ask_human", result["decision"])
        self.assertEqual("owner_capability_required", result["reason_code"])

    def test_local_missing_capability_requests_repair(self):
        state = base_state()
        state["todos"][0]["required_capabilities"] = ["benchmark_runner"]
        result = controller.evaluate(state, now=NOW)
        self.assertEqual("blocked", result["decision"])
        self.assertEqual("capability_repair", result["effective_action"])
        self.assertTrue(result["must_attempt_work"])
        self.assertFalse(result["normal_delivery_allowed"])

    def test_active_other_lease_skips_to_next_todo(self):
        state = base_state()
        state["todos"] = [
            {
                "id": "todo-a",
                "status": "claimed",
                "task_class": "advancement_task",
                "required_capabilities": [],
                "lease": {
                    "id": "lease-other",
                    "owner": "worker-b",
                    "expires_at": "2026-08-12T05:00:00Z",
                },
            },
            {
                "id": "todo-b",
                "status": "unclaimed",
                "task_class": "advancement_task",
                "required_capabilities": [],
            },
        ]
        result = controller.evaluate(state, now=NOW)
        self.assertEqual("todo-b", result["selected_todo"]["id"])
        self.assertEqual("todo_leased_by_other", result["diagnostics"][0]["code"])

    def test_expired_lease_becomes_runnable(self):
        state = base_state()
        state["todos"][0]["lease"] = {
            "id": "lease-old",
            "owner": "worker-b",
            "expires_at": "2026-08-12T03:00:00Z",
        }
        result = controller.evaluate(state, now=NOW)
        self.assertEqual("run", result["decision"])
        self.assertEqual("expired", result["runnable_candidates"][0]["lease_state"])

    @patch.object(controller.uuid, "uuid4")
    def test_claim_projects_bounded_lease(self, uuid4_mock):
        uuid4_mock.return_value.hex = "abc123"
        result = controller.claim(base_state(), now=NOW, lease_seconds=900)
        self.assertEqual("ok", result["status"])
        self.assertEqual("lease-abc123", result["claim"]["lease"]["id"])
        self.assertEqual("worker-a", result["claim"]["lease"]["owner"])
        self.assertEqual("2026-08-12T04:15:00+00:00", result["claim"]["lease"]["expires_at"])

    def test_spend_requires_validated_writeback_and_evidence(self):
        state = base_state()
        state["previous_slice"] = {
            "writeback_complete": True,
            "validated": False,
            "evidence_refs": ["e-1"],
        }
        result = controller.spend(state, slots=1)
        self.assertEqual("invalid_transition", result["status"])
        self.assertEqual("slice_unvalidated", result["reason_code"])

        state["previous_slice"]["validated"] = True
        state["previous_slice"]["evidence_refs"] = []
        result = controller.spend(state, slots=1)
        self.assertEqual("evidence_missing", result["reason_code"])

    def test_spend_updates_projection_only_after_validated_writeback(self):
        state = base_state()
        state["previous_slice"] = {
            "writeback_complete": True,
            "validated": True,
            "evidence_refs": ["e-1"],
        }
        state["quota"]["spent_slots"] = 10
        result = controller.spend(state, slots=3)
        self.assertEqual("ok", result["status"])
        self.assertEqual(13, result["quota"]["spent_slots"])
        self.assertEqual(["e-1"], result["evidence_refs"])

    def test_non_graph_mode_is_rejected(self):
        state = base_state()
        state["execution_mode"] = "prompt"
        with self.assertRaises(controller.ContractError):
            controller.evaluate(state, now=NOW)


if __name__ == "__main__":
    unittest.main()
