from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "Tools"
    / "ExecutionOrchestrator"
    / "execution_orchestrator.py"
)
spec = importlib.util.spec_from_file_location("execution_orchestrator_ticket_semantics", MODULE_PATH)
orchestrator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(orchestrator)


class ExecutionOrchestratorTicketSemanticTests(unittest.TestCase):
    def ticket(self, profile: str, work_kind: str, *, paths=None, evidence_refs=None, scope="portable_artifact"):
        value = {
            "schema_version": "1.4",
            "goal_id": "goal-1",
            "selected_todo_id": "todo-1",
            "worker_id": "worker-1",
            "execution_profile": profile,
            "work_kind": work_kind,
            "state_fingerprint": "0" * 64,
            "source_verification": {
                "completed": True,
                "scope_class": scope,
                "paths": paths or [],
                "evidence_refs": evidence_refs or [],
            },
            "ticket_id": "ticket-" + "1" * 24,
        }
        value["ticket_digest"] = orchestrator._digest(
            {key: item for key, item in value.items() if key != "ticket_digest"}
        )
        return value

    def test_valid_portable_import_ticket_semantics_pass(self):
        ticket = self.ticket(
            "team_safe_import",
            "portable_import",
            paths=[],
            evidence_refs=["portable-verification-1"],
        )
        orchestrator._verify_ticket(ticket)
        orchestrator._validate_ticket_semantics(ticket)

    def test_recomputed_digest_does_not_make_team_safe_local_path_valid(self):
        ticket = self.ticket(
            "team_safe_import",
            "portable_import",
            paths=["CompanyProject/Assets/Secret.cs"],
            evidence_refs=["portable-verification-1"],
        )
        orchestrator._verify_ticket(ticket)
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator._validate_ticket_semantics(ticket)
        self.assertEqual(caught.exception.code, "ticket_semantics_invalid")

    def test_recomputed_digest_does_not_make_generic_mutation_valid(self):
        ticket = self.ticket(
            "generic_planning",
            "mutation",
            paths=[],
            evidence_refs=["ev-1"],
        )
        orchestrator._verify_ticket(ticket)
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator._validate_ticket_semantics(ticket)
        self.assertIn(caught.exception.code, {"work_kind_profile_forbidden", "ticket_semantics_invalid"})

    def test_personal_mutation_requires_source_path_and_evidence(self):
        ticket = self.ticket(
            "personal_full_control",
            "mutation",
            paths=[],
            evidence_refs=[],
            scope="project_internal",
        )
        orchestrator._verify_ticket(ticket)
        with self.assertRaises(orchestrator.OrchestrationError) as caught:
            orchestrator._validate_ticket_semantics(ticket)
        self.assertEqual(caught.exception.code, "ticket_semantics_invalid")


if __name__ == "__main__":
    unittest.main()
