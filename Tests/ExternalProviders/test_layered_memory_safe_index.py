from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "Tools"
    / "LayeredMemoryController"
    / "layered_memory_controller.py"
)
spec = importlib.util.spec_from_file_location("layered_memory_safe_index", MODULE_PATH)
memory = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(memory)


class LayeredMemorySafeIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def capture(self, evidence_id: str, scope: str, content: str):
        source = self.workspace / f"{evidence_id}.txt"
        source.write_text(content, encoding="utf-8")
        return memory.execute(
            self.workspace,
            {
                "operation": "capture_raw",
                "evidence_id": evidence_id,
                "source_file": str(source),
                "source_type": "test_result",
                "execution_profile": "personal_full_control",
                "scope_class": scope,
            },
        )

    def test_safe_index_contains_only_non_internal_records(self):
        self.capture("ev-internal", "project_internal", "internal evidence")
        self.capture("ev-portable", "portable_artifact", "portable evidence")
        entries = memory._safe_index_entries(self.workspace)
        self.assertNotIn("ev-internal", entries)
        self.assertIn("ev-portable", entries)
        self.assertEqual(entries["ev-portable"]["scope_class"], "portable_artifact")

    def test_team_safe_retrieval_never_opens_internal_record_file(self):
        self.capture("ev-internal", "project_internal", "internal renderer evidence")
        self.capture("ev-portable", "portable_artifact", "portable renderer evidence")
        internal_path = memory._record_path(self.workspace, "L0_raw_evidence", "ev-internal")
        portable_path = memory._record_path(self.workspace, "L0_raw_evidence", "ev-portable")
        original = memory._read_json
        opened: list[Path] = []

        def tracked(path: Path):
            opened.append(path)
            return original(path)

        with mock.patch.object(memory, "_read_json", side_effect=tracked):
            result = memory.execute(
                self.workspace,
                {
                    "operation": "retrieve",
                    "execution_profile": "team_safe_import",
                    "query": "renderer",
                },
            )

        self.assertEqual(result["status"], "ok")
        self.assertNotIn(internal_path, opened)
        self.assertIn(portable_path, opened)

    def test_unindexed_legacy_record_is_not_opened_by_team_safe(self):
        path = memory._record_path(self.workspace, "L1_atom", "legacy-portable-looking")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "memory_id": "legacy-portable-looking",
                    "layer": "L1_atom",
                    "created_at": "legacy",
                    "statement": "looks portable but has no trusted index",
                    "raw_refs": [],
                    "atom_refs": [],
                    "scenario_refs": [],
                    "applicability": [],
                    "limits": [],
                    "confidence": "verified",
                    "provenance": [],
                    "promotion_target": "none",
                    "review_status": "not_required",
                    "supersedes": [],
                    "conflicts_with": [],
                    "execution_profile": "personal_full_control",
                    "scope_class": "portable_artifact",
                }
            ),
            encoding="utf-8",
        )
        original = memory._read_json
        opened: list[Path] = []

        def tracked(record_path: Path):
            opened.append(record_path)
            return original(record_path)

        with mock.patch.object(memory, "_read_json", side_effect=tracked):
            result = memory.execute(
                self.workspace,
                {
                    "operation": "retrieve",
                    "execution_profile": "team_safe_import",
                    "query": "portable",
                },
            )
        self.assertEqual(result["data"]["item_count"], 0)
        self.assertNotIn(path, opened)

    def test_corrupt_safe_index_fails_closed(self):
        index = memory._safe_index_path(self.workspace)
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(
            json.dumps(
                {
                    "memory_id": "bad",
                    "layer": "L1_atom",
                    "scope_class": "project_internal",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            memory.execute(
                self.workspace,
                {
                    "operation": "retrieve",
                    "execution_profile": "team_safe_import",
                    "query": "anything",
                },
            )
        self.assertEqual(caught.exception.code, "safe_index_corrupt")


if __name__ == "__main__":
    unittest.main()
