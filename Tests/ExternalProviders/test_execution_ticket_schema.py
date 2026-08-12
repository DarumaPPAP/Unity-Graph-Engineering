from __future__ import annotations

import unittest
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator, ValidationError
except ImportError:  # Local stdlib-only runs may omit CI schema dependencies.
    yaml = None
    Draft202012Validator = None
    ValidationError = Exception


@unittest.skipUnless(yaml is not None and Draft202012Validator is not None, "pyyaml/jsonschema not installed")
class ExecutionTicketSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[2]
        schema_path = root / "schemas" / "execution-ticket.schema.yaml"
        cls.schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def ticket(self, profile: str, work_kind: str, source: dict) -> dict:
        return {
            "schema_version": "1.4",
            "goal_id": "goal-1",
            "selected_todo_id": "todo-1",
            "worker_id": "worker-1",
            "execution_profile": profile,
            "work_kind": work_kind,
            "state_fingerprint": "0" * 64,
            "source_verification": source,
            "ticket_id": "ticket-" + "1" * 24,
            "ticket_digest": "2" * 64,
        }

    def test_personal_mutation_ticket_is_valid(self):
        self.validator.validate(
            self.ticket(
                "personal_full_control",
                "mutation",
                {
                    "completed": True,
                    "scope_class": "project_internal",
                    "paths": ["Assets/Feature.cs"],
                    "evidence_refs": ["source-read-1"],
                },
            )
        )

    def test_team_safe_portable_import_ticket_is_valid(self):
        self.validator.validate(
            self.ticket(
                "team_safe_import",
                "portable_import",
                {
                    "completed": True,
                    "scope_class": "portable_artifact",
                    "paths": [],
                    "evidence_refs": ["portable-verification-1"],
                },
            )
        )

    def test_team_safe_ticket_with_local_path_is_invalid(self):
        with self.assertRaises(ValidationError):
            self.validator.validate(
                self.ticket(
                    "team_safe_import",
                    "portable_import",
                    {
                        "completed": True,
                        "scope_class": "portable_artifact",
                        "paths": ["CompanyProject/Assets/Secret.cs"],
                        "evidence_refs": ["portable-verification-1"],
                    },
                )
            )

    def test_generic_mutation_ticket_is_invalid(self):
        with self.assertRaises(ValidationError):
            self.validator.validate(
                self.ticket(
                    "generic_planning",
                    "mutation",
                    {
                        "completed": True,
                        "scope_class": "portable_artifact",
                        "paths": [],
                        "evidence_refs": ["ev-1"],
                    },
                )
            )


if __name__ == "__main__":
    unittest.main()
