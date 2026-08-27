from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "Tools" / "BehaviorEvalAdapter" / "run_production_smoke.py"
FAKE_AGENT = ROOT / "Tests" / "BehaviorEvalAdapter" / "fake_production_agent.py"


class ProductionSmokeLauncherTests(unittest.TestCase):
    def _make_unityagent_root(self, temp: Path) -> Path:
        unityagent = temp / "UnityAgent"
        runner = unityagent / "Tools" / "BehaviorEval" / "run_behavior_eval.py"
        runner.parent.mkdir(parents=True)
        runner.write_text(
            "from __future__ import annotations\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "root = Path(__file__).resolve().parents[2]\n"
            "(root / 'captured.json').write_text(json.dumps({\n"
            "    'argv': sys.argv[1:],\n"
            "    'production_command': os.environ.get('UNITYAGENT_PRODUCTION_COMMAND_JSON', ''),\n"
            "}, indent=2) + '\\n', encoding='utf-8')\n"
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        suites = unityagent / "Tests" / "BehaviorEval" / "suites.yaml"
        suites.parent.mkdir(parents=True)
        suites.write_text("schema_version: '1.0'\nsuites:\n  production_smoke: {}\n", encoding="utf-8")
        return unityagent

    def test_launcher_wires_production_smoke_to_strict_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            unityagent = self._make_unityagent_root(temp)
            command = json.dumps([sys.executable, str(temp / "real_agent.py")])

            completed = subprocess.run(
                [
                    sys.executable,
                    str(LAUNCHER),
                    "--unityagent-root",
                    str(unityagent),
                    "--agent-command-json",
                    command,
                    "--run-id",
                    "phase1-contract",
                    "--timeout-seconds",
                    "123",
                ],
                cwd=ROOT,
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            captured = json.loads((unityagent / "captured.json").read_text(encoding="utf-8"))
            argv = captured["argv"]
            self.assertEqual(argv[argv.index("--suite") + 1], "production_smoke")
            self.assertEqual(argv[argv.index("--run-id") + 1], "phase1-contract")
            self.assertIn("--executor-command", argv)
            self.assertIn("--require-production-identity", argv)
            self.assertIn("--timeout-seconds", argv)
            self.assertEqual(captured["production_command"], command)

    def test_launcher_rejects_repository_fake_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            unityagent = self._make_unityagent_root(temp)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(LAUNCHER),
                    "--unityagent-root",
                    str(unityagent),
                    "--agent-command-json",
                    json.dumps([sys.executable, str(FAKE_AGENT)]),
                ],
                cwd=ROOT,
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(completed.returncode, 30)
            self.assertIn("refuses the repository fake Production Agent fixture", completed.stderr)
            self.assertFalse((unityagent / "captured.json").exists())

    def test_launcher_requires_real_agent_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            unityagent = self._make_unityagent_root(temp)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(LAUNCHER),
                    "--unityagent-root",
                    str(unityagent),
                ],
                cwd=ROOT,
                check=False,
                text=True,
                capture_output=True,
                env={},
            )

            self.assertEqual(completed.returncode, 30)
            self.assertIn("Real Production Agent command is required", completed.stderr)


if __name__ == "__main__":
    unittest.main()
