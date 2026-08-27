from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools" / "UnityAgentCompatibility"))

from handoff_adapter import build_state_patch, validate_handoff  # noqa: E402


class UnityAgentHandoffV2Tests(unittest.TestCase):
    def _document(self, decision: str = "within_budget", *, mutating: bool = True) -> dict:
        return {
            "schema_version": "2.0",
            "task_id": "task-1",
            "context_manifest_id": "manifest-1",
            "context_manifest_schema_version": "3.1",
            "route_id": "csharp-local-fix",
            "task_fingerprint": {
                "intent": "fix",
                "artifact": "csharp",
                "scope": "local",
                "failure_mode": "compile",
                "architecture_state": "existing",
                "mutation_target": "source",
                "evidence_state": "compile",
                "project_access": "personal_full_control",
            },
            "task_contract_ref": ".ai/harness/task-contracts/csharp-local-fix.yaml",
            "execution_profile": "personal_full_control",
            "risk_level": "R1" if mutating else "R0",
            "selected_contexts": [{"id": "csharp-local-fix", "source_hash": "abc"}],
            "context_budget_decision": {
                "contract": ".ai/context-budget.yaml",
                "profile": "tight",
                "decision": decision,
                "blocking_reasons": [],
            },
            "allowed_mutations": ["source_edit"] if mutating else [],
            "prohibited_mutations": ["project_settings"],
            "required_quality_gates": ["static_review", "compile"],
            "conditional_quality_gates": ["playmode"],
            "unresolved_bindings": [],
        }

    def test_valid_handoff_projects_losslessly(self) -> None:
        document = self._document()
        self.assertEqual(validate_handoff(document), [])
        patch = build_state_patch(document)
        self.assertEqual(patch["domain_route"], "csharp-local-fix")
        self.assertEqual(patch["task_contract_id"], "csharp-local-fix")
        self.assertEqual(patch["unityagent_handoff"]["context_manifest_id"], "manifest-1")
        self.assertEqual(patch["unityagent_handoff"]["required_quality_gates"], ["static_review", "compile"])
        self.assertTrue(patch["mutation_allowed_by_context_budget"])

    def test_mutation_is_blocked_when_context_budget_is_not_within_budget(self) -> None:
        document = self._document("compression_required")
        self.assertIn("mutation requires UnityAgent context budget within_budget", validate_handoff(document))

    def test_read_only_handoff_may_preserve_nonpassing_context_budget_status(self) -> None:
        document = self._document("unmeasured", mutating=False)
        self.assertEqual(validate_handoff(document), [])
        self.assertFalse(build_state_patch(document)["mutation_allowed_by_context_budget"])


if __name__ == "__main__":
    unittest.main()
