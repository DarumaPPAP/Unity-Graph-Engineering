from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "Tools" / "CodexProductionAgent" / "codex_production_agent_v2.py"
FAKE_CODEX = ROOT / "Tests" / "BehaviorEvalAdapter" / "fake_codex_cli.py"


class CodexProductionAgentV2Tests(unittest.TestCase):
    def _make_unityagent_root(self, temp: Path) -> Path:
        root = temp / "UnityAgent"
        contracts = root / ".ai" / "harness" / "task-contracts"
        contracts.mkdir(parents=True)
        (root / ".agents").mkdir()
        (root / "SkillReferences").mkdir()
        (root / "AGENTS.md").write_text("# UnityAgent\nRead .ai/user-policy.yaml.\n", encoding="utf-8")
        (root / ".ai" / "user-policy.yaml").write_text(
            yaml.safe_dump({
                "core_user_policies": {
                    "minimum_cohesive_solution_first": {
                        "rule": "Choose the minimum cohesive solution."
                    }
                }
            }, sort_keys=False),
            encoding="utf-8",
        )
        (contracts / "architecture-design.yaml").write_text(
            yaml.safe_dump({
                "id": "architecture-design",
                "required_quality_gates": ["architecture_fit", "file_granularity"],
                "conditional_quality_gates": [],
            }, sort_keys=False),
            encoding="utf-8",
        )
        return root

    def _request(self, workspace: Path) -> dict:
        return {
            "schema_version": "1.0",
            "task": {"summary": "Review a local CameraDebugger architecture without mutation."},
            "execution": {
                "mode": "prompt",
                "profile": "generic_planning",
                "work_kind": "analysis",
                "max_agent_attempts": 1,
            },
            "workspace_root": str(workspace),
            "mutation_scope": {"allowed_paths": [], "prohibited_paths": []},
            "evidence_contract": {
                "require": ["response", "context_manifest", "artifact_index"],
                "optional": ["gate_evidence"],
            },
            "observed_evidence": [],
            "primary_focus": "architecture",
            "evidence_output": "unused-by-bridge",
            "unityagent_revision": "fixture-revision",
            "golden_task_id": "GOLDEN-ARCH-001",
        }

    def _run(
        self,
        temp: Path,
        *,
        policy_id: str | None = None,
        policy_source: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        workspace = temp / "workspace"
        workspace.mkdir()
        (workspace / "CameraDebugger.cs").write_text(
            "public sealed class CameraDebugger { }\n", encoding="utf-8"
        )
        request_path = temp / "request.json"
        output = temp / "evidence"
        request_path.write_text(json.dumps(self._request(workspace), ensure_ascii=False), encoding="utf-8")

        env = os.environ.copy()
        env["UNITYAGENT_ROOT"] = str(self._make_unityagent_root(temp))
        if policy_id is not None:
            env["FAKE_CODEX_POLICY_ID"] = policy_id
        if policy_source is not None:
            env["FAKE_CODEX_POLICY_SOURCE"] = policy_source

        command = [
            sys.executable,
            str(BRIDGE),
            "--request",
            str(request_path),
            "--output",
            str(output),
            "--model",
            "gpt-5.6-luna",
            "--codex-command-json",
            json.dumps([sys.executable, str(FAKE_CODEX)]),
            "--timeout-seconds",
            "30",
            "--reasoning-effort",
            "high",
        ]
        return subprocess.run(command, cwd=ROOT, check=False, text=True, capture_output=True, env=env)

    def test_full_yaml_policy_fragment_completes_v2_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            completed = self._run(temp)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            metadata = yaml.safe_load(
                (temp / "evidence" / "execution-metadata.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata.get("failure_class", ""), "")
            manifest = yaml.safe_load(
                (temp / "evidence" / "context-manifest.yaml").read_text(encoding="utf-8")
            )
            loaded = manifest.get("policy", {}).get("loaded", [])
            self.assertTrue(any(
                item.get("id") == "minimum_cohesive_solution_first"
                and item.get("source_path", "").endswith(
                    "#core_user_policies.minimum_cohesive_solution_first"
                )
                for item in loaded
            ))

    def test_real_production_qualified_id_shape_is_normalized_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            completed = self._run(
                temp,
                policy_id=(
                    ".ai/user-policy.yaml"
                    "#core_user_policies.minimum_cohesive_solution_first"
                ),
                policy_source=".unityagent-control/.ai/user-policy.yaml",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            metadata = yaml.safe_load(
                (temp / "evidence" / "execution-metadata.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata.get("failure_class", ""), "")
            manifest = yaml.safe_load(
                (temp / "evidence" / "context-manifest.yaml").read_text(encoding="utf-8")
            )
            loaded = manifest.get("policy", {}).get("loaded", [])
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].get("id"), "minimum_cohesive_solution_first")
            self.assertEqual(
                loaded[0].get("source_path"),
                ".unityagent-control/.ai/user-policy.yaml#core_user_policies.minimum_cohesive_solution_first",
            )

    def test_invalid_yaml_parent_is_evaluator_contract_failure_after_codex_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            completed = self._run(
                temp,
                policy_source=(
                    ".unityagent-control/.ai/user-policy.yaml"
                    "#wrong_parent.minimum_cohesive_solution_first"
                ),
            )

            self.assertEqual(completed.returncode, 30)
            self.assertIn("Policy clause id/source fragment mismatch", completed.stderr)
            metadata = yaml.safe_load(
                (temp / "evidence" / "execution-metadata.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata.get("failure_class"), "evaluator_contract_failure")
            metrics = json.loads((temp / "evidence" / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics.get("failure_class"), "evaluator_contract_failure")

    def test_qualified_id_with_conflicting_source_document_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            root = self._make_unityagent_root(temp)
            (root / ".ai" / "other-policy.yaml").write_text(
                yaml.safe_dump({
                    "core_user_policies": {
                        "minimum_cohesive_solution_first": {
                            "rule": "Other document."
                        }
                    }
                }, sort_keys=False),
                encoding="utf-8",
            )

            workspace = temp / "workspace"
            workspace.mkdir()
            (workspace / "CameraDebugger.cs").write_text(
                "public sealed class CameraDebugger { }\n", encoding="utf-8"
            )
            request_path = temp / "request.json"
            output = temp / "evidence"
            request_path.write_text(json.dumps(self._request(workspace), ensure_ascii=False), encoding="utf-8")
            env = os.environ.copy()
            env["UNITYAGENT_ROOT"] = str(root)
            env["FAKE_CODEX_POLICY_ID"] = (
                ".ai/user-policy.yaml#core_user_policies.minimum_cohesive_solution_first"
            )
            env["FAKE_CODEX_POLICY_SOURCE"] = ".unityagent-control/.ai/other-policy.yaml"
            command = [
                sys.executable,
                str(BRIDGE),
                "--request",
                str(request_path),
                "--output",
                str(output),
                "--model",
                "gpt-5.6-luna",
                "--codex-command-json",
                json.dumps([sys.executable, str(FAKE_CODEX)]),
                "--timeout-seconds",
                "30",
                "--reasoning-effort",
                "high",
            ]
            completed = subprocess.run(
                command, cwd=ROOT, check=False, text=True, capture_output=True, env=env
            )

            self.assertEqual(completed.returncode, 30)
            self.assertIn("Policy id/source document mismatch", completed.stderr)
            metadata = yaml.safe_load(
                (output / "execution-metadata.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata.get("failure_class"), "evaluator_contract_failure")


if __name__ == "__main__":
    unittest.main()
