from __future__ import annotations

import json
import unittest
from pathlib import Path


class ControlPlaneExampleTests(unittest.TestCase):
    def test_orchestrator_examples_are_valid_json_objects(self):
        root = Path(__file__).resolve().parents[2]
        paths = [
            root / "examples" / "execution-orchestrator-personal-prepare.json",
            root / "examples" / "execution-orchestrator-team-safe-portable-import.json",
            root / "examples" / "continuation-controller-input.json",
            root / "examples" / "layered-memory-capture.json",
        ]
        for path in paths:
            with self.subTest(path=path.name):
                value = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(value, dict)

    def test_team_safe_example_has_no_local_source_paths_or_ix(self):
        root = Path(__file__).resolve().parents[2]
        path = root / "examples" / "execution-orchestrator-team-safe-portable-import.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(value["execution_profile"], "team_safe_import")
        self.assertEqual(value["work_kind"], "portable_import")
        self.assertEqual(value["source_verification"]["paths"], [])
        self.assertTrue(value["source_verification"]["evidence_refs"])
        self.assertEqual(value["source_verification"]["scope_class"], "portable_artifact")
        self.assertFalse(value["code_intelligence"]["enabled"])

    def test_personal_mutation_example_binds_source_read_evidence(self):
        root = Path(__file__).resolve().parents[2]
        path = root / "examples" / "execution-orchestrator-personal-prepare.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(value["execution_profile"], "personal_full_control")
        self.assertEqual(value["work_kind"], "mutation")
        self.assertTrue(value["source_verification"]["paths"])
        self.assertTrue(value["source_verification"]["evidence_refs"])
        self.assertEqual(value["source_verification"]["scope_class"], "project_internal")


if __name__ == "__main__":
    unittest.main()
