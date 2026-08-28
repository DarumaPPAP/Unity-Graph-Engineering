from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ADAPTER_DIR = ROOT / "Tools" / "BehaviorEvalAdapter"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTER_DIR))

import behavior_eval_adapter_v2 as adapter  # noqa: E402


class MutationNoopEnvelopeTests(unittest.TestCase):
    def test_mutation_zero_change_is_reclassified_as_agent_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            staging = Path(temp_dir)
            (staging / "metrics.json").write_text(
                json.dumps({"changed_paths": []}), encoding="utf-8"
            )
            metadata = {
                "status": "completed",
                "execution_class": "production",
                "agent_id": "codex-cli",
                "provider": "openai",
                "model": "gpt-5.6-luna",
            }

            patched = adapter._enforce_mutation_noop_classification(
                work_kind="mutation",
                staging=staging,
                metadata=metadata,
                process_returncode=0,
                timed_out=False,
            )

            self.assertEqual(patched.get("status"), "failed")
            self.assertEqual(patched.get("failure_class"), "agent_behavior_regression")
            self.assertIn("without changing any workspace file", patched.get("failure_reason", ""))

    def test_allowed_mutation_is_not_reclassified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            staging = Path(temp_dir)
            (staging / "metrics.json").write_text(
                json.dumps({"changed_paths": ["CameraDebugger.cs"]}), encoding="utf-8"
            )
            metadata = {"status": "completed"}

            patched = adapter._enforce_mutation_noop_classification(
                work_kind="mutation",
                staging=staging,
                metadata=metadata,
                process_returncode=0,
                timed_out=False,
            )

            self.assertEqual(patched, metadata)

    def test_infrastructure_failure_is_never_reclassified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            staging = Path(temp_dir)
            (staging / "metrics.json").write_text(
                json.dumps({"changed_paths": []}), encoding="utf-8"
            )
            metadata = {
                "status": "failed",
                "failure_class": "runtime_protocol_failure",
            }

            patched = adapter._enforce_mutation_noop_classification(
                work_kind="mutation",
                staging=staging,
                metadata=metadata,
                process_returncode=30,
                timed_out=False,
            )

            self.assertEqual(patched, metadata)

    def test_exit_10_without_child_failure_class_stays_agent_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            publish = Path(temp_dir)
            (publish / "context-manifest.yaml").write_text("{}\n", encoding="utf-8")
            (publish / "response.md").write_text("noop\n", encoding="utf-8")
            (publish / "artifact-index.yaml").write_text(
                yaml.safe_dump({"schema_version": "1.0", "artifacts": []}), encoding="utf-8"
            )
            request = {
                "run_id": "mutation-noop",
                "golden_task_id": "GOLDEN-MUTATION-001",
                "unityagent_revision": "fixture",
                "execution": {"profile": "personal_full_control"},
            }
            metadata = {
                "status": "failed",
                "execution_class": "production",
                "agent_id": "codex-cli",
                "provider": "openai",
                "model": "gpt-5.6-luna",
                "infrastructure_attempts": 1,
            }

            adapter._write_envelope_v2(
                request,
                publish,
                command=["codex"],
                fixture_hash="fixture-hash",
                mode="prompt",
                metadata=metadata,
                process_returncode=10,
                adapter_runtime={},
            )

            envelope = yaml.safe_load(
                (publish / "execution-envelope.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(envelope.get("status"), "failed")
            self.assertEqual(
                (envelope.get("failure", {}) or {}).get("class"),
                "agent_behavior_regression",
            )
            self.assertEqual(
                (envelope.get("failure", {}) or {}).get("observation_state"),
                "observed",
            )


if __name__ == "__main__":
    unittest.main()
