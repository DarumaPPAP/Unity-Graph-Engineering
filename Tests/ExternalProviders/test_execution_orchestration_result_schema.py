from __future__ import annotations

import unittest
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except ImportError:
    yaml = None
    Draft202012Validator = None
    Registry = None
    Resource = None


@unittest.skipUnless(
    yaml is not None and Draft202012Validator is not None and Registry is not None,
    "pyyaml/jsonschema/referencing not installed",
)
class ExecutionOrchestrationResultSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[2]
        result_schema = yaml.safe_load(
            (root / "schemas" / "execution-orchestration-result.schema.yaml").read_text(encoding="utf-8")
        )
        ticket_schema = yaml.safe_load(
            (root / "schemas" / "execution-ticket.schema.yaml").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(result_schema)
        Draft202012Validator.check_schema(ticket_schema)
        registry = Registry().with_resource(
            "execution-ticket.schema.yaml",
            Resource.from_contents(ticket_schema),
        )
        cls.validator = Draft202012Validator(result_schema, registry=registry)

    def test_ready_personal_mutation_prepare_result_matches_runtime_contract(self):
        value = {
            "schema_version": "1.4",
            "controller": "execution_orchestrator",
            "operation": "prepare",
            "status": "ok",
            "ready_for_execution": True,
            "decision": {"should_run": True},
            "claim": None,
            "memory": None,
            "code_intelligence": None,
            "source_verification": {
                "completed": True,
                "required": True,
                "scope_class": "project_internal",
                "paths": ["Assets/Feature.cs"],
                "evidence_refs": ["source-read-1"],
            },
            "ticket": {
                "schema_version": "1.4",
                "goal_id": "goal-1",
                "selected_todo_id": "todo-1",
                "worker_id": "worker-1",
                "execution_profile": "personal_full_control",
                "work_kind": "mutation",
                "state_fingerprint": "0" * 64,
                "source_verification": {
                    "completed": True,
                    "scope_class": "project_internal",
                    "paths": ["Assets/Feature.cs"],
                    "evidence_refs": ["source-read-1"],
                },
                "ticket_id": "ticket-" + "1" * 24,
                "ticket_digest": "2" * 64,
            },
            "evidence": None,
            "atom": None,
            "quota": None,
            "required_state_writeback": None,
            "required_next_action": "execute_one_bounded_slice",
            "diagnostics": [],
            "authority": {
                "owns_source_mutation": False,
                "owns_state_current": False,
                "owns_human_gate": False,
                "owns_quota_policy": False,
                "coordinates_controllers": True,
            },
        }
        self.validator.validate(value)

    def test_ready_team_safe_portable_import_prepare_result_matches_runtime_contract(self):
        value = {
            "schema_version": "1.4",
            "controller": "execution_orchestrator",
            "operation": "prepare",
            "status": "ok",
            "ready_for_execution": True,
            "decision": {"should_run": True},
            "claim": None,
            "memory": None,
            "code_intelligence": None,
            "source_verification": {
                "completed": True,
                "required": True,
                "scope_class": "portable_artifact",
                "paths": [],
                "evidence_refs": ["portable-verification-1"],
            },
            "ticket": {
                "schema_version": "1.4",
                "goal_id": "goal-1",
                "selected_todo_id": "todo-1",
                "worker_id": "worker-1",
                "execution_profile": "team_safe_import",
                "work_kind": "portable_import",
                "state_fingerprint": "0" * 64,
                "source_verification": {
                    "completed": True,
                    "scope_class": "portable_artifact",
                    "paths": [],
                    "evidence_refs": ["portable-verification-1"],
                },
                "ticket_id": "ticket-" + "1" * 24,
                "ticket_digest": "2" * 64,
            },
            "evidence": None,
            "atom": None,
            "quota": None,
            "required_state_writeback": None,
            "required_next_action": "execute_one_bounded_slice",
            "diagnostics": [],
            "authority": {
                "owns_source_mutation": False,
                "owns_state_current": False,
                "owns_human_gate": False,
                "owns_quota_policy": False,
                "coordinates_controllers": True,
            },
        }
        self.validator.validate(value)


if __name__ == "__main__":
    unittest.main()
