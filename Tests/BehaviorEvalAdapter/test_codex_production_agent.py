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
BRIDGE = ROOT / "Tools" / "CodexProductionAgent" / "codex_production_agent.py"
FAKE_CODEX = ROOT / "Tests" / "BehaviorEvalAdapter" / "fake_codex_cli.py"


class CodexProductionAgentTests(unittest.TestCase):
    def _make_unityagent_root(self, temp: Path) -> Path:
        root = temp / "UnityAgent"
        (root / ".ai").mkdir(parents=True)
        (root / ".agents" / "skills" / "unity-architecture-design").mkdir(parents=True)
        (root / "SkillReferences").mkdir()
        (root / "AGENTS.md").write_text("# UnityAgent\nRead .ai/context-index.yaml.\n", encoding="utf-8")
        (root / ".ai" / "context-index.yaml").write_text(
            "schema_version: '3.3'\nuser_policy: .ai/user-policy.yaml\n", encoding="utf-8"
        )
        (root / ".ai" / "user-policy.yaml").write_text(
            "minimum_cohesive_solution_first: true\n", encoding="utf-8"
        )
        (root / ".agents" / "skills" / "unity-architecture-design" / "SKILL.md").write_text(
            "Use the smallest cohesive architecture.\n", encoding="utf-8"
        )
        (root / "SkillReferences" / "ARCHITECTURE_STANDARDS.md").write_text(
            "Avoid speculative managers.\n", encoding="utf-8"
        )
        return root

    def _request(self, workspace: Path, *, work_kind: str, allowed_paths: list[str] | None = None) -> dict:
        return {
            "schema_version": "1.0",
            "task": {"summary": "一つのComponent内で完結する小規模Local Behavior"},
            "execution": {
                "mode": "prompt",
                "profile": "generic_planning" if work_kind == "analysis" else "personal_full_control",
                "work_kind": work_kind,
                "max_agent_attempts": 1,
            },
            "workspace_root": str(workspace),
            "mutation_scope": {
                "allowed_paths": allowed_paths or [],
                "prohibited_paths": [],
            },
            "evidence_contract": {
                "require": ["response", "context_manifest", "artifact_index"],
                "optional": ["diff", "gate_evidence"],
            },
            "evidence_output": "unused-by-bridge",
            "unityagent_revision": "abc123",
            "golden_task_id": "GOLDEN-ARCH-001",
        }

    def _run(self, temp: Path, request: dict, *, mutate: str | None = None) -> subprocess.CompletedProcess[str]:
        request_path = temp / "request.json"
        output = temp / "evidence"
        request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
        env = os.environ.copy()
        env["UNITYAGENT_ROOT"] = str(self._make_unityagent_root(temp))
        if mutate:
            env["FAKE_CODEX_MUTATE"] = mutate
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
        ]
        return subprocess.run(command, cwd=ROOT, check=False, text=True, capture_output=True, env=env)

    def test_bridge_emits_real_identity_and_behavior_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            workspace = temp / "workspace"
            workspace.mkdir()
            (workspace / "CameraDebugger.cs").write_text(
                "public sealed class CameraDebugger { }\n", encoding="utf-8"
            )

            completed = self._run(temp, self._request(workspace, work_kind="analysis"))

            self.assertEqual(completed.returncode, 0, completed.stderr)
            output = temp / "evidence"
            metadata = yaml.safe_load((output / "execution-metadata.yaml").read_text(encoding="utf-8"))
            self.assertEqual(metadata["execution_class"], "production")
            self.assertEqual(metadata["agent_id"], "codex-cli")
            self.assertEqual(metadata["provider"], "openai")
            self.assertEqual(metadata["model"], "gpt-5.6-luna")
            manifest = yaml.safe_load((output / "context-manifest.yaml").read_text(encoding="utf-8"))
            self.assertEqual(manifest["task"]["route"], "architecture-design")
            self.assertTrue((output / "generated" / "CameraDebugger.cs").is_file())
            self.assertFalse((output / "generated" / ".unityagent-control").exists())

    def test_bridge_generates_diff_for_allowed_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            workspace = temp / "workspace"
            workspace.mkdir()
            (workspace / "CameraDebugger.cs").write_text(
                "public sealed class CameraDebugger { }\n", encoding="utf-8"
            )
            request = self._request(workspace, work_kind="mutation", allowed_paths=["CameraDebugger.cs"])

            completed = self._run(temp, request, mutate="CameraDebugger.cs")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            diff = (temp / "evidence" / "diff.patch").read_text(encoding="utf-8")
            self.assertIn("CameraDebugger.cs", diff)
            metrics = json.loads((temp / "evidence" / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["changed_paths"], ["CameraDebugger.cs"])

    def test_bridge_fails_closed_on_out_of_scope_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            workspace = temp / "workspace"
            workspace.mkdir()
            (workspace / "CameraDebugger.cs").write_text(
                "public sealed class CameraDebugger { }\n", encoding="utf-8"
            )
            request = self._request(workspace, work_kind="mutation", allowed_paths=["CameraDebugger.cs"])

            completed = self._run(temp, request, mutate="Unexpected.cs")

            self.assertEqual(completed.returncode, 30)
            self.assertIn("Mutation escaped allowed paths", completed.stderr)
            metadata = yaml.safe_load((temp / "evidence" / "execution-metadata.yaml").read_text(encoding="utf-8"))
            self.assertEqual(metadata["status"], "failed")


if __name__ == "__main__":
    unittest.main()
