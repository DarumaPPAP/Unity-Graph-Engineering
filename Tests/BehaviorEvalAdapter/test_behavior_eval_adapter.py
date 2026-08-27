from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "Tools" / "BehaviorEvalAdapter" / "behavior_eval_adapter.py"
FAKE_AGENT = ROOT / "Tests" / "BehaviorEvalAdapter" / "fake_production_agent.py"


class BehaviorEvalAdapterTests(unittest.TestCase):
    def test_adapter_runs_production_command_once_and_emits_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            unityagent_root = temp / "UnityAgent"
            fixture = unityagent_root / "Tests" / "BehaviorEval" / "Fixtures" / "CameraDebugger"
            fixture.mkdir(parents=True)
            (fixture / "CameraDebugger.cs").write_text("public class CameraDebugger { }\n", encoding="utf-8")

            request = {
                "schema_version": "1.0",
                "run_id": "behavior-test",
                "golden_task_id": "GOLDEN-NAMING-001",
                "unityagent_revision": "fixture-unityagent-sha",
                "task": {"prompt": "fixture"},
                "execution": {
                    "mode": "prompt",
                    "profile": "generic_planning",
                    "work_kind": "analysis",
                    "max_agent_attempts": 1,
                },
                "workspace": {
                    "fixture": "Tests/BehaviorEval/Fixtures/CameraDebugger",
                    "mutation_mode": "sandbox",
                },
                "evidence": {
                    "require": ["response", "context_manifest", "artifact_index"],
                    "optional": ["diff", "gate_evidence"],
                },
                "result_root": "Artifacts/BehaviorEval/behavior-test",
            }
            request_path = temp / "request.yaml"
            request_path.write_text(yaml.safe_dump(request, sort_keys=False), encoding="utf-8")
            output = temp / "output"
            command = json.dumps([sys.executable, str(FAKE_AGENT)])

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ADAPTER),
                    "--request",
                    str(request_path),
                    "--output",
                    str(output),
                    "--unityagent-root",
                    str(unityagent_root),
                    "--agent-command-json",
                    command,
                ],
                cwd=ROOT,
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            envelope = yaml.safe_load((output / "execution-envelope.yaml").read_text(encoding="utf-8"))
            self.assertEqual(envelope["execution_owner"]["repository"], "DarumaPPAP/Unity-Graph-Engineering")
            self.assertEqual(envelope["unityagent"]["revision"], "fixture-unityagent-sha")
            self.assertEqual(envelope["executor"]["mode"], "prompt")
            self.assertEqual(envelope["attempt"]["agent_attempt"], 1)
            self.assertEqual(envelope["status"], "completed")
            self.assertTrue((output / "generated" / "CameraDebugger.cs").is_file())
            self.assertTrue((output / "context-manifest.yaml").is_file())
            self.assertNotIn("workspace_root", envelope)

    def test_adapter_rejects_graph_alias_and_requires_production_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            unityagent_root = temp / "UnityAgent"
            fixture = unityagent_root / "Tests" / "BehaviorEval" / "Fixtures" / "CameraDebugger"
            fixture.mkdir(parents=True)
            request = {
                "schema_version": "1.0",
                "run_id": "behavior-test",
                "golden_task_id": "GOLDEN-ARCH-001",
                "unityagent_revision": "fixture",
                "task": {},
                "execution": {
                    "mode": "graph",
                    "profile": "generic_planning",
                    "work_kind": "analysis",
                    "max_agent_attempts": 1,
                },
                "workspace": {
                    "fixture": "Tests/BehaviorEval/Fixtures/CameraDebugger",
                    "mutation_mode": "sandbox",
                },
                "evidence": {},
                "result_root": "Artifacts/BehaviorEval/behavior-test",
            }
            request_path = temp / "request.yaml"
            request_path.write_text(yaml.safe_dump(request, sort_keys=False), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ADAPTER),
                    "--request",
                    str(request_path),
                    "--output",
                    str(temp / "output"),
                    "--unityagent-root",
                    str(unityagent_root),
                    "--agent-command-json",
                    json.dumps([sys.executable, str(FAKE_AGENT)]),
                ],
                cwd=ROOT,
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 30)
            self.assertIn("Unsupported production execution mode", completed.stderr)


if __name__ == "__main__":
    unittest.main()
