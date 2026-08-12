from __future__ import annotations

import importlib.util
import io
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
            "execution_profile": "personal_full_control",
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
            "execution_profile": "personal_full_control",
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
            "execution_profile": "personal_full_control",
            "created_at": "2026-08-12T00:03:00+00:00",
        }
        request.update(overrides)
        return memory.execute(self.workspace, request)

    def build_chain(self, scope_class="project_internal"):
        self.capture(scope_class=scope_class)
        profile = "personal_full_control" if scope_class == "project_internal" else "team_safe_import"
        self.atom(execution_profile=profile)
        self.scenario(execution_profile=profile)
        self.candidate(execution_profile=profile)

    def test_capture_preserves_raw_and_sha256(self):
        result = self.capture()
        self.assertEqual(result["status"], "ok")
        raw_path = self.workspace / "Evidence/raw/ev-1.txt"
        self.assertEqual(raw_path.read_text(encoding="utf-8"), "compile passed")
        self.assertEqual(len(result["data"]["sha256"]), 64)

    def test_same_id_same_content_is_idempotent(self):
        self.capture()
        result = self.capture()
        self.assertFalse(result["mutated"])

    def test_same_id_different_content_is_blocked(self):
        self.capture()
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            self.capture(content="different")
        self.assertEqual(caught.exception.code, "id_conflict")

    def test_secret_capture_is_blocked(self):
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            self.capture(content="api_key=abcdefghijklmnop123456")
        self.assertEqual(caught.exception.code, "secret_capture_forbidden")

    def test_team_safe_scope_blocks_before_source_file_access(self):
        missing = self.workspace / "missing-secret.txt"
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            memory.execute(
                self.workspace,
                {
                    "operation": "capture_raw",
                    "evidence_id": "ev-safe",
                    "source_file": str(missing),
                    "execution_profile": "team_safe_import",
                    "scope_class": "project_internal",
                },
            )
        self.assertEqual(caught.exception.code, "memory_scope_forbidden")

    def test_generic_scope_blocks_project_internal_capture(self):
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            self.capture(execution_profile="generic_planning")
        self.assertEqual(caught.exception.code, "memory_scope_forbidden")

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

    def test_scope_is_inherited_across_layers(self):
        self.build_chain()
        for memory_id in ("atom-1", "scenario-1", "candidate-1"):
            self.assertEqual(memory._load_record(self.workspace, memory_id)["scope_class"], "project_internal")

    def test_scope_downgrade_is_blocked(self):
        self.capture()
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            self.atom(scope_class="public_reference")
        self.assertEqual(caught.exception.code, "scope_downgrade_forbidden")

    def test_conflict_is_preserved_without_overwrite(self):
        self.capture("ev-a", "A")
        self.capture("ev-b", "B")
        self.atom("atom-a", ["ev-a"], statement="A")
        self.atom("atom-b", ["ev-b"], statement="B", conflicts_with=["atom-a"])
        self.assertEqual(memory._load_record(self.workspace, "atom-a")["conflicts_with"], [])
        self.assertEqual(memory._load_record(self.workspace, "atom-b")["conflicts_with"], ["atom-a"])

    def test_supersede_preserves_old_record(self):
        self.capture("ev-a", "A")
        self.capture("ev-b", "B")
        self.atom("atom-a", ["ev-a"], statement="old")
        self.atom("atom-b", ["ev-b"], statement="new", supersedes=["atom-a"])
        self.assertTrue((self.workspace / "STATE/memory/L1/atom-a.json").is_file())

    def test_retrieve_prefers_higher_layer_and_never_includes_raw_content(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {
                "operation": "retrieve",
                "execution_profile": "personal_full_control",
                "query": "renderer verification",
            },
        )
        self.assertEqual(result["data"]["items"][0]["layer"], "L3_reusable_candidate")
        self.assertFalse(result["data"]["raw_content_included"])

    def test_retrieve_is_bounded_by_item_count(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {
                "operation": "retrieve",
                "execution_profile": "personal_full_control",
                "query": "",
                "max_items": 2,
                "max_chars": 6000,
            },
        )
        self.assertEqual(result["data"]["item_count"], 2)
        self.assertTrue(result["data"]["truncated"])

    def test_team_safe_retrieve_filters_project_internal_memory(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {
                "operation": "retrieve",
                "execution_profile": "team_safe_import",
                "query": "renderer verification",
            },
        )
        self.assertEqual(result["data"]["item_count"], 0)
        self.assertTrue(any(item["code"] == "memory_scope_filtered" for item in result["diagnostics"]))

    def test_generic_retrieve_filters_project_internal_memory(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {
                "operation": "retrieve",
                "execution_profile": "generic_planning",
                "query": "renderer verification",
            },
        )
        self.assertEqual(result["data"]["item_count"], 0)

    def test_legacy_record_without_scope_is_treated_as_internal(self):
        path = self.workspace / "STATE/memory/L1/legacy.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "memory_id": "legacy",
                    "layer": "L1_atom",
                    "created_at": "legacy",
                    "statement": "renderer verification",
                    "confidence": "verified",
                }
            ),
            encoding="utf-8",
        )
        result = memory.execute(
            self.workspace,
            {
                "operation": "retrieve",
                "execution_profile": "team_safe_import",
                "query": "renderer verification",
            },
        )
        self.assertEqual(result["data"]["item_count"], 0)

    def test_portable_chain_is_visible_to_team_safe(self):
        self.build_chain(scope_class="portable_artifact")
        result = memory.execute(
            self.workspace,
            {
                "operation": "retrieve",
                "execution_profile": "team_safe_import",
                "query": "renderer verification",
            },
        )
        self.assertGreater(result["data"]["item_count"], 0)

    def test_drilldown_reaches_l0_for_personal(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {
                "operation": "drilldown",
                "execution_profile": "personal_full_control",
                "memory_id": "candidate-1",
                "max_chars": 12000,
            },
        )
        self.assertEqual(
            [record["layer"] for record in result["data"]["records"]],
            ["L3_reusable_candidate", "L2_scenario", "L1_atom", "L0_raw_evidence"],
        )

    def test_team_safe_drilldown_cannot_open_internal_memory(self):
        self.build_chain()
        with self.assertRaises(memory.MemoryErrorContract) as caught:
            memory.execute(
                self.workspace,
                {
                    "operation": "drilldown",
                    "execution_profile": "team_safe_import",
                    "memory_id": "candidate-1",
                },
            )
        self.assertEqual(caught.exception.code, "memory_scope_forbidden")

    def test_raw_content_requires_explicit_drilldown(self):
        self.build_chain()
        compact = memory.execute(
            self.workspace,
            {
                "operation": "drilldown",
                "execution_profile": "personal_full_control",
                "memory_id": "candidate-1",
            },
        )
        self.assertFalse(compact["data"]["raw_content_included"])
        expanded = memory.execute(
            self.workspace,
            {
                "operation": "drilldown",
                "execution_profile": "personal_full_control",
                "memory_id": "candidate-1",
                "include_raw_content": True,
                "max_chars": 12000,
            },
        )
        raw = [item for item in expanded["data"]["records"] if item["layer"] == "L0_raw_evidence"][0]
        self.assertEqual(raw["raw_content"], "compile passed")

    def test_project_is_compact_and_source_of_truth_is_explicit(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {
                "operation": "project",
                "execution_profile": "personal_full_control",
                "query": "renderer",
                "projection_id": "p-1",
            },
        )
        self.assertFalse(result["data"]["raw_content_included"])
        self.assertIn("STATE/current.yaml", result["data"]["source_of_truth"])

    def test_unverified_candidate_cannot_promote_to_unityagent_knowledge(self):
        self.capture()
        self.atom()
        self.scenario()
        self.candidate(confidence="unverified")
        result = memory.execute(
            self.workspace,
            {
                "operation": "promote",
                "execution_profile": "personal_full_control",
                "memory_id": "candidate-1",
                "target": "unityagent_knowledge",
            },
        )
        self.assertEqual(result["status"], "blocked")

    def test_user_policy_candidate_requires_human_gate(self):
        self.capture()
        self.atom()
        self.scenario()
        self.candidate(promotion_target="user_policy_candidate")
        result = memory.execute(
            self.workspace,
            {
                "operation": "promote",
                "execution_profile": "personal_full_control",
                "memory_id": "candidate-1",
                "target": "user_policy_candidate",
            },
        )
        self.assertEqual(result["status"], "blocked")

    def test_promotion_never_writes_unityagent(self):
        self.build_chain()
        result = memory.execute(
            self.workspace,
            {
                "operation": "promote",
                "execution_profile": "personal_full_control",
                "memory_id": "candidate-1",
                "target": "unityagent_knowledge",
            },
        )
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["mutated"])
        self.assertFalse(result["data"]["writes_external_authority"])

    def test_cli_request_can_be_read_from_stdin(self):
        payload = json.dumps(
            {
                "operation": "retrieve",
                "execution_profile": "generic_planning",
                "query": "renderer",
            }
        )
        with mock.patch("sys.stdin", io.StringIO(payload)):
            request = memory._read_request("-")
        self.assertEqual(request["operation"], "retrieve")


if __name__ == "__main__":
    unittest.main()
