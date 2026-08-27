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
    def _make_unityagent_root(self, temp: Path) -> Path:
        unityagent_root = temp / "UnityAgent"
        (unityagent_root / ".ai").mkdir(parents=True)
        (unityagent_root / "AGENTS.md").write_text("# Fixture UnityAgent\n", encoding="utf-8")
        fixture = unityagent_root / "Tests" / "BehaviorEval" / "Fixtures" / "CameraDebugger"
        fixture.mkdir(parents=True)
        (fixture / "CameraDebugger.cs").write_text("public class CameraDebugger { }\n", encoding="utf-8")
        return unityagent_root

    def _request(self, *, mode: str = "prompt") -> dict:
        return {
            "schema_version": "1.0",
            "run_id": "behavior-test",
            "golden_task_id": "GOLDEN-NAMING-001",
            "unityagent_revision": "fixture-unityagent-sha",
            "task": {"prompt": "fixture"},
            "execution": {
                "mode": mode,
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

    def _run_adapter(
        self,
        temp: Path,
        unityagent_root: Path,
        request: dict,
        *,
        output: Path | None = None,
        agent_args: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        request_path = temp / "request.yaml"
        request_path.write_text(yaml.safe_dump(request, sort_keys=False), encoding="utf-8")
        output = output or (temp / "output")
        command = json.dumps([sys.executable, str(FAKE_AGENT), *(agent_args or [])])
        argv = [
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
        ]
        if timeout_seconds is not None:
            argv.extend(["--timeout-seconds", str(timeout_seconds)])
        return subprocess.run(
            argv,
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )

    def test_adapter_runs_production_command_once_and_emits_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            unityagent_root = self._make_unityagent_root(temp)
            output = temp / "output"

            completed = self._run_adapter(temp, unityagent_root, self._request(), output=output)

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

    def test_nonzero_process_exit_is_authoritative_over_completed_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            unityagent_root = self._make_unityagent_root(temp)
            output = temp / "output"

            completed = self._run_adapter(
                temp,
                unityagent_root,
                self._request(),
                output=output,
                agent_args=["--exit-code", "7", "--status", "completed"],
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            envelope = yaml.safe_load((output / "execution-envelope.yaml").read_text(encoding="utf-8"))
            self.assertEqual(envelope["status"], "failed")

    def test_adapter_rejects_stale_managed_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            unityagent_root = self._make_unityagent_root(temp)
            output = temp / "output"
            output.mkdir()
            (output / "diff.patch").write_text("stale evidence\n", encoding="utf-8")

            completed = self._run_adapter(temp, unityagent_root, self._request(), output=output)

            self.assertEqual(completed.returncode, 30)
            self.assertIn("output must be fresh", completed.stderr)
            self.assertFalse((output / "execution-envelope.yaml").exists())
            self.assertEqual((output / "diff.patch").read_text(encoding="utf-8"), "stale evidence\n")

    def test_adapter_times_out_production_agent_without_publishing_partial_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            unityagent_root = self._make_unityagent_root(temp)
            output = temp / "output"

            completed = self._run_adapter(
                temp,
                unityagent_root,
                self._request(),
                output=output,
                agent_args=["--sleep-seconds", "1"],
                timeout_seconds=0.05,
            )

            self.assertEqual(completed.returncode, 30)
            self.assertIn("timed out", completed.stderr)
            self.assertFalse((output / "execution-envelope.yaml").exists())
            self.assertFalse((output / "response.md").exists())
            self.assertFalse((output / "generated").exists())

    def test_adapter_rejects_graph_alias_and_requires_production_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            unityagent_root = self._make_unityagent_root(temp)

            completed = self._run_adapter(temp, unityagent_root, self._request(mode="graph"))

            self.assertEqual(completed.returncode, 30)
            self.assertIn("Unsupported production execution mode", completed.stderr)

    def test_adapter_requires_explicit_unityagent_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            request_path = temp / "request.yaml"
            request_path.write_text(yaml.safe_dump(self._request(), sort_keys=False), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ADAPTER),
                    "--request",
                    str(request_path),
                    "--output",
                    str(temp / "output"),
                    "--agent-command-json",
                    json.dumps([sys.executable, str(FAKE_AGENT)]),
                ],
                cwd=ROOT,
                check=False,
                text=True,
                capture_output=True,
                env={},
            )
            self.assertEqual(completed.returncode, 30)
            self.assertIn("UnityAgent checkout root is required", completed.stderr)


if __name__ == "__main__":
    unittest.main()
