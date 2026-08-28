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


class RequiredMutationExecutionTests(unittest.TestCase):
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
            "task": {
                "summary": "Fix the known local compile error.",
                "production_prompt": "CameraDebugger.cs の既知Compile Errorだけを最小Patchで修正してください。",
            },
            "execution": {
                "mode": "prompt",
                "profile": "personal_full_control",
                "work_kind": "mutation",
                "max_agent_attempts": 1,
            },
            "workspace_root": str(workspace),
            "mutation_scope": {
                "allowed_paths": ["CameraDebugger.cs"],
                "prohibited_paths": [],
            },
            "evidence_contract": {
                "require": ["response", "context_manifest", "artifact_index", "diff"],
                "optional": ["gate_evidence"],
            },
            "observed_evidence": [],
            "primary_focus": "mutation",
            "evidence_output": "unused-by-bridge",
            "unityagent_revision": "fixture-revision",
            "golden_task_id": "GOLDEN-MUTATION-001",
        }

    def _run(self, temp: Path, *, mutate: bool) -> tuple[subprocess.CompletedProcess[str], Path]:
        workspace = temp / "workspace"
        workspace.mkdir()
        (workspace / "CameraDebugger.cs").write_text(
            "public sealed class CameraDebugger { public int Broken => Missing; }\n",
            encoding="utf-8",
        )
        request_path = temp / "request.json"
        output = temp / "evidence"
        request_path.write_text(json.dumps(self._request(workspace), ensure_ascii=False), encoding="utf-8")

        env = os.environ.copy()
        env["UNITYAGENT_ROOT"] = str(self._make_unityagent_root(temp))
        if mutate:
            env["FAKE_CODEX_MUTATE"] = "CameraDebugger.cs"

        command = [
            sys.executable,
            str(BRIDGE),
            "--request", str(request_path),
            "--output", str(output),
            "--model", "gpt-5.6-luna",
            "--codex-command-json", json.dumps([sys.executable, str(FAKE_CODEX)]),
            "--timeout-seconds", "30",
            "--reasoning-effort", "high",
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
        return completed, output

    def test_mutation_work_with_zero_changes_is_agent_behavior_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            completed, output = self._run(Path(temp_dir), mutate=False)
            self.assertEqual(completed.returncode, 10, completed.stderr)
            metadata = yaml.safe_load((output / "execution-metadata.yaml").read_text(encoding="utf-8"))
            self.assertEqual(metadata.get("failure_class"), "agent_behavior_regression")
            metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics.get("changed_paths"), [])
            response = (output / "response.md").read_text(encoding="utf-8")
            self.assertIn("without changing any workspace file", response)

    def test_mutation_work_with_allowed_change_completes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            completed, output = self._run(Path(temp_dir), mutate=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            metadata = yaml.safe_load((output / "execution-metadata.yaml").read_text(encoding="utf-8"))
            self.assertEqual(metadata.get("failure_class", ""), "")
            metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics.get("changed_paths"), ["CameraDebugger.cs"])


if __name__ == "__main__":
    unittest.main()
