from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CODEX_TOOLS = ROOT / "Tools" / "CodexProductionAgent"
if str(CODEX_TOOLS) not in sys.path:
    sys.path.insert(0, str(CODEX_TOOLS))

import codex_production_agent as legacy  # noqa: E402
import codex_production_agent_v2 as bridge  # noqa: E402
from process_runtime import utf8_child_env  # noqa: E402


class Phase11HardeningTests(unittest.TestCase):
    def _control(self, temp: Path) -> Path:
        control = temp / ".unityagent-control"
        contracts = control / ".ai" / "harness" / "task-contracts"
        contracts.mkdir(parents=True)
        (control / ".ai" / "user-policy.yaml").write_text(
            yaml.safe_dump({
                "core_user_policies": {
                    "engineering_principles": {"priority": "critical"},
                    "minimum_cohesive_solution_first": {"priority": "critical"},
                    "evidence_scoped_claims": {"priority": "critical"},
                }
            }, sort_keys=False),
            encoding="utf-8",
        )
        (contracts / "architecture-design.yaml").write_text(
            yaml.safe_dump({
                "id": "architecture-design",
                "required_quality_gates": ["architecture_fit", "file_granularity"],
                "conditional_quality_gates": ["compile", "playmode"],
            }, sort_keys=False),
            encoding="utf-8",
        )
        (contracts / "csharp-local-fix.yaml").write_text(
            yaml.safe_dump({
                "id": "csharp-local-fix",
                "required_quality_gates": ["static_review", "compile"],
                "conditional_quality_gates": ["playmode"],
            }, sort_keys=False),
            encoding="utf-8",
        )
        return control

    def test_policy_provenance_accepts_exact_full_yaml_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            control = self._control(Path(temp_dir))
            structured = {
                "loaded_policies": [{
                    "id": "minimum_cohesive_solution_first",
                    "source_path": ".unityagent-control/.ai/user-policy.yaml#core_user_policies.minimum_cohesive_solution_first",
                    "reason": "minimum cohesive solution",
                }]
            }
            bridge._validate_policies(control, structured)
            self.assertEqual(structured["loaded_policies"][0]["id"], "minimum_cohesive_solution_first")

    def test_policy_provenance_normalizes_real_production_qualified_id_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            control = self._control(Path(temp_dir))
            structured = {
                "loaded_policies": [{
                    "id": ".ai/user-policy.yaml#core_user_policies.engineering_principles",
                    "source_path": ".unityagent-control/.ai/user-policy.yaml",
                    "reason": "KISS/YAGNI and responsibility-depth policy",
                }]
            }

            bridge._validate_policies(control, structured)

            policy = structured["loaded_policies"][0]
            self.assertEqual(policy["id"], "engineering_principles")
            self.assertEqual(
                policy["source_path"],
                ".unityagent-control/.ai/user-policy.yaml#core_user_policies.engineering_principles",
            )

    def test_policy_provenance_keeps_unique_leaf_fragment_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            control = self._control(Path(temp_dir))
            structured = {
                "loaded_policies": [{
                    "id": "minimum_cohesive_solution_first",
                    "source_path": ".ai/user-policy.yaml#minimum_cohesive_solution_first",
                    "reason": "legacy unique leaf fragment",
                }]
            }
            bridge._validate_policies(control, structured)
            self.assertEqual(structured["loaded_policies"][0]["id"], "minimum_cohesive_solution_first")

    def test_policy_provenance_rejects_wrong_parent_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            control = self._control(Path(temp_dir))
            invalid = {
                "loaded_policies": [{
                    "id": "minimum_cohesive_solution_first",
                    "source_path": ".ai/user-policy.yaml#wrong_parent.minimum_cohesive_solution_first",
                    "reason": "wrong YAML path",
                }]
            }
            with self.assertRaises(legacy.CodexProductionAgentError):
                bridge._validate_policies(control, invalid)

    def test_policy_provenance_rejects_document_id_without_clause_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            control = self._control(Path(temp_dir))
            invalid = {
                "loaded_policies": [{
                    "id": "user-policy",
                    "source_path": ".ai/user-policy.yaml",
                    "reason": "document id only",
                }]
            }
            with self.assertRaises(legacy.CodexProductionAgentError):
                bridge._validate_policies(control, invalid)

    def test_policy_provenance_rejects_ambiguous_leaf_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            control = self._control(Path(temp_dir))
            policy_path = control / ".ai" / "user-policy.yaml"
            policy_path.write_text(
                yaml.safe_dump({
                    "core_user_policies": {
                        "minimum_cohesive_solution_first": {"priority": "critical"},
                    },
                    "legacy": {
                        "minimum_cohesive_solution_first": {"priority": "legacy"},
                    },
                }, sort_keys=False),
                encoding="utf-8",
            )
            invalid = {
                "loaded_policies": [{
                    "id": "minimum_cohesive_solution_first",
                    "source_path": ".ai/user-policy.yaml#minimum_cohesive_solution_first",
                    "reason": "ambiguous leaf fragment",
                }]
            }
            with self.assertRaises(legacy.CodexProductionAgentError):
                bridge._validate_policies(control, invalid)

            exact = {
                "loaded_policies": [{
                    "id": "minimum_cohesive_solution_first",
                    "source_path": ".ai/user-policy.yaml#core_user_policies.minimum_cohesive_solution_first",
                    "reason": "exact path remains valid",
                }]
            }
            bridge._validate_policies(control, exact)

    def test_qualified_policy_id_rejects_different_source_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            control = self._control(Path(temp_dir))
            other = control / ".ai" / "other-policy.yaml"
            other.write_text(
                yaml.safe_dump({
                    "core_user_policies": {
                        "engineering_principles": {"priority": "other"},
                    }
                }, sort_keys=False),
                encoding="utf-8",
            )
            invalid = {
                "loaded_policies": [{
                    "id": ".ai/user-policy.yaml#core_user_policies.engineering_principles",
                    "source_path": ".unityagent-control/.ai/other-policy.yaml",
                    "reason": "conflicting documents",
                }]
            }
            with self.assertRaises(legacy.CodexProductionAgentError):
                bridge._validate_policies(control, invalid)

    def test_qualified_policy_id_rejects_conflicting_source_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            control = self._control(Path(temp_dir))
            invalid = {
                "loaded_policies": [{
                    "id": ".ai/user-policy.yaml#core_user_policies.engineering_principles",
                    "source_path": ".unityagent-control/.ai/user-policy.yaml#core_user_policies.evidence_scoped_claims",
                    "reason": "conflicting fragments",
                }]
            }
            with self.assertRaises(legacy.CodexProductionAgentError):
                bridge._validate_policies(control, invalid)

    def test_optional_unavailable_gate_does_not_fail_architecture_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            control = self._control(Path(temp_dir))
            request = {"execution": {"work_kind": "analysis"}, "observed_evidence": []}
            structured = {
                "route": "architecture-design",
                "quality_gates": [
                    {"id": "architecture_fit", "requirement": "required", "status": "passed", "evidence": "review"},
                    {"id": "file_granularity", "requirement": "required", "status": "passed", "evidence": "review"},
                    {"id": "compile", "requirement": "not_applicable", "status": "unavailable", "evidence": "not requested"},
                ],
                "execution_evidence": [],
            }
            status = bridge._resolve_gates(control, request, structured)
            self.assertEqual(status, "passed")
            compile_gate = next(item for item in structured["quality_gates"] if item["id"] == "compile")
            self.assertEqual(compile_gate["requirement"], "not_applicable")

    def test_verification_uses_trusted_compile_evidence_as_completion_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            control = self._control(Path(temp_dir))
            request = {
                "execution": {"work_kind": "verification"},
                "observed_evidence": [{
                    "id": "compile-fixture",
                    "gate": "compile",
                    "status": "passed",
                    "source": "fixture",
                    "statement": "C# compile completed with 0 errors",
                }],
            }
            structured = {
                "route": "csharp-local-fix",
                "quality_gates": [
                    {"id": "static_review", "requirement": "required", "status": "unavailable", "evidence": "not performed"},
                ],
                "execution_evidence": [],
            }
            status = bridge._resolve_gates(control, request, structured)
            self.assertEqual(status, "passed")
            compile_gate = next(item for item in structured["quality_gates"] if item["id"] == "compile")
            static_gate = next(item for item in structured["quality_gates"] if item["id"] == "static_review")
            self.assertEqual(compile_gate["requirement"], "required")
            self.assertEqual(compile_gate["status"], "passed")
            self.assertEqual(static_gate["requirement"], "not_applicable")

    def test_utf8_environment_is_forced(self) -> None:
        env = utf8_child_env({"EXISTING": "1"})
        self.assertEqual(env["PYTHONUTF8"], "1")
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(env["EXISTING"], "1")

    def test_launchers_pin_reasoning_and_support_single_case(self) -> None:
        codex_launcher = (ROOT / "Tools" / "CodexProductionAgent" / "run_codex_production_smoke.py").read_text(encoding="utf-8")
        behavior_launcher = (ROOT / "Tools" / "BehaviorEvalAdapter" / "run_production_smoke.py").read_text(encoding="utf-8")
        self.assertIn('default="high"', codex_launcher)
        self.assertIn('"--case", "--only-case"', codex_launcher)
        self.assertIn('"--case", "--only-case"', behavior_launcher)
        self.assertIn("behavior_eval_adapter_v2.py", behavior_launcher)


if __name__ == "__main__":
    unittest.main()
