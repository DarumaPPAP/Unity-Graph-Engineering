from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "Tools"
    / "LayeredMemoryController"
    / "layered_memory_controller.py"
)
spec = importlib.util.spec_from_file_location("layered_memory_controller", MODULE_PATH)
memory = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(memory)


class LayeredMemoryControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def capture(self, evidence_id="ev-1", content="compile passed", **overrides):
        source = self.workspace / f"{evidence_id}.txt"
        source.write_text(content, encoding="utf-8")
        request = {
            "operation": "capture_raw",
            "evidence_id": evidence_id,
            "source_file": str(source),
            "source_type": "test_result",
            "execution_profile": "personal_full_control",
            "scope_class": "project_internal",
            "created_at": "2026-08-12T00:00:00+00:00",
        }
        request.update(overrides)
        return memory.execute(self.workspace, request)

    def atom(self, memory_id="atom-1", raw_refs=None, **overrides):
        request = {
            "operation": "create_atom",
            "memory_id": memory_id,
            "statement": "Compile succeeds after patch",
            "raw_refs": raw_refs or ["ev-1"],
            "confidence": "verified",
            "created_at": "2026-08-12T00:01:00+00:00",
        }
        request.update(overrides)
        return memory.execute(self.workspace, request)

    def scenario(self, memory_id="scenario-1", atom_refs=None, **overrides):
        request = {
            "operation": "create_scenario",
            "memory_id": memory_id,
            "statement": "Renderer patch verification",
            "atom_refs": atom_refs or ["atom-1"],
            "confidence": "verified",
            "applicability": ["Unity 6 URP"],
            "limits": ["Requires direct source verification"],
            "created_at": "2026-08-12T00:02:00+00:00",
        }
        request.update(overrides)
        return memory.execute(self.workspace, request)

    def candidate(self, memory_id="candidate-1", scenario_refs=None, **overrides):
        request = {
            "operation": "create_candidate",
            "memory_id": memory_id,
            "statement": "Reusable renderer verification workflow",
            "scenario_refs": scenario_refs or ["scenario-1"],
            "confidence": "verified",
            "provenance": ["run-1", "ev-1"],
            "promotion_target": "unityagent_knowledge",
            "review_status": "approved",
            "created_at": "2026-08-12T00:03:00+00:00",
        }
        request.update(overrides)
        return memory.execute(self.workspace, request)

    def build_chain(self):
        self.capture()
        self.atom()
        self.scenario()
        self.candidate()

    def test_capture_preserves_raw_and_sha256(self):
        result = self.capture()
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["mutated"])
        raw_path = self.workspace / "Evidence/raw/ev-1.txt"
        self.assertEqual(raw_path.read_text(encoding="utf-8"), "compile passed")
        self.assertEqual(len(result["data"]["sha256"]), 64)

    def test_capture_same_id_same_content_is_idempotent(self):
        self.capture()
        result = self.capture()
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["mutated"])

    def test_capture_same_id_same_content_is_idempotent_without_fixed_timestamp(self):
        source = self.workspace / "dynamic.txt"
        source.write_text("same", encoding="utf-8")
        request = {
            "operation": "capture_raw",
            "evidence_id": "ev-dynamic",
            "source_file": str(source),
            "source_type": "test_result",
            "execution_profile": "personal_full_control",
            "scope_class": "project_internal",
        }
        first = memory.execute(self.workspace, request)
        second = memory.execute(self.workspace, request)
        self.assertTrue(first["mutated"])
        self.assertFalse(second["mutated"])

    def test_capture_same_id_different_content_is_blocked(self):
        self.capture()
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            self.capture(content="different")
        self.assertEqual(caught.exception.code, "id_conflict")

    def test_secret_capture_is_blocked(self):
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            self.capture(content="api_key=abcdefghijklmnop123456")
        self.assertEqual(caught.exception.code, "secret_capture_forbidden")

    def test_team_safe_rejects_project_internal_capture(self):
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            self.capture(execution_profile="team_safe_import", scope_class="project_internal")
        self.assertEqual(caught.exception.code, "team_safe_scope_forbidden")

    def test_team_safe_scope_blocks_before_source_file_access(self):
        request = {
            "operation": "capture_raw",
            "evidence_id": "ev-forbidden",
            "source_file": str(self.workspace / "does-not-exist.txt"),
            "execution_profile": "team_safe_import",
            "scope_class": "project_internal",
        }
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            memory.execute(self.workspace, request)
        self.assertEqual(caught.exception.code, "team_safe_scope_forbidden")

    def test_atom_requires_l0_reference(self):
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            self.atom()
        self.assertEqual(caught.exception.code, "memory_not_found")

    def test_scenario_requires_l1_reference(self):
        self.capture()
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            self.scenario(atom_refs=["ev-1"])
        self.assertEqual(caught.exception.code, "invalid_reference_layer")

    def test_candidate_requires_provenance(self):
        self.capture()
        self.atom()
        self.scenario()
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            self.candidate(provenance=[])
        self.assertEqual(caught.exception.code, "missing_provenance")

    def test_conflict_is_preserved_without_overwriting_old_record(self):
        self.capture("ev-a", "A")
        self.capture("ev-b", "B")
        self.atom("atom-a", ["ev-a"], statement="A is true")
        self.atom("atom-b", ["ev-b"], statement="B is true", conflicts_with=["atom-a"])
        old = memory._load_record(self.workspace, "atom-a")
        new = memory._load_record(self.workspace, "atom-b")
        self.assertEqual(old["conflicts_with"], [])
        self.assertEqual(new["conflicts_with"], ["atom-a"])

    def test_supersede_relation_does_not_delete_old_record(self):
        self.capture("ev-a", "A")
        self.capture("ev-b", "B")
        self.atom("atom-a", ["ev-a"], statement="old")
        self.atom("atom-b", ["ev-b"], statement="new", supersedes=["atom-a"])
        self.assertTrue((self.workspace / "STATE/memory/L1/atom-a.json").is_file())
        self.assertEqual(memory._load_record(self.workspace, "atom-b")["supersedes"], ["atom-a"])

    def test_retrieve_prefers_higher_layer_and_never_includes_raw_content(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {"operation": "retrieve", "query": "renderer verification", "max_items": 8, "max_chars": 6000},
        )
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["data"]["raw_content_included"])
        self.assertEqual(result["data"]["items"][0]["layer"], "L3_reusable_candidate")
        self.assertTrue(all("raw_content" not in item for item in result["data"]["items"]))

    def test_retrieve_is_bounded_by_item_count(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {"operation": "retrieve", "query": "", "max_items": 2, "max_chars": 6000},
        )
        self.assertEqual(result["data"]["item_count"], 2)
        self.assertTrue(result["data"]["truncated"])

    def test_drilldown_reaches_l0(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {"operation": "drilldown", "memory_id": "candidate-1", "max_chars": 12000},
        )
        layers = [record["layer"] for record in result["data"]["records"]]
        self.assertEqual(
            layers,
            ["L3_reusable_candidate", "L2_scenario", "L1_atom", "L0_raw_evidence"],
        )
        self.assertFalse(result["data"]["raw_content_included"])

    def test_raw_content_requires_explicit_drilldown_flag(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {
                "operation": "drilldown",
                "memory_id": "candidate-1",
                "include_raw_content": True,
                "max_chars": 12000,
            },
        )
        raw_records = [record for record in result["data"]["records"] if record["layer"] == "L0_raw_evidence"]
        self.assertEqual(raw_records[0]["raw_content"], "compile passed")

    def test_project_is_compact_and_source_of_truth_is_explicit(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {"operation": "project", "query": "renderer", "projection_id": "p-1"},
        )
        self.assertEqual(result["operation"], "project")
        self.assertFalse(result["data"]["raw_content_included"])
        self.assertIn("STATE/current.yaml", result["data"]["source_of_truth"])

    def test_unverified_candidate_cannot_promote_to_unityagent_knowledge(self):
        self.capture()
        self.atom()
        self.scenario()
        self.candidate(confidence="unverified")
        result = memory.execute(
            self.workspace,
            {"operation": "promote", "memory_id": "candidate-1", "target": "unityagent_knowledge"},
        )
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["data"]["approved"])

    def test_user_policy_candidate_requires_human_gate(self):
        self.capture()
        self.atom()
        self.scenario()
        self.candidate(promotion_target="user_policy_candidate")
        result = memory.execute(
            self.workspace,
            {"operation": "promote", "memory_id": "candidate-1", "target": "user_policy_candidate"},
        )
        self.assertEqual(result["status"], "blocked")
        approved = memory.execute(
            self.workspace,
            {
                "operation": "promote",
                "memory_id": "candidate-1",
                "target": "user_policy_candidate",
                "human_gate_approved": True,
            },
        )
        self.assertEqual(approved["status"], "ok")
        self.assertFalse(approved["data"]["writes_external_authority"])

    def test_promotion_never_writes_unityagent(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {"operation": "promote", "memory_id": "candidate-1", "target": "unityagent_knowledge"},
        )
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["mutated"])
        self.assertFalse(result["data"]["writes_external_authority"])


if __name__ == "__main__":
    unittest.main()
