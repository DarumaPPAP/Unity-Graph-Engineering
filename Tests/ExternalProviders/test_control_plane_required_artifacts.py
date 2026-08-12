from __future__ import annotations

import unittest
from pathlib import Path


class ControlPlaneRequiredArtifactsTests(unittest.TestCase):
    def test_required_control_plane_artifacts_exist(self):
        root = Path(__file__).resolve().parents[2]
        required = [
            ".gitignore",
            "policies/external-providers.yaml",
            "policies/continuation-control.yaml",
            "policies/memory-layering.yaml",
            "policies/execution-orchestration.yaml",
            "schemas/execution-state.schema.yaml",
            "schemas/continuation-state.schema.yaml",
            "schemas/memory-layer.schema.yaml",
            "schemas/execution-ticket.schema.yaml",
            "schemas/execution-orchestration-result.schema.yaml",
            "Tools/IxAdapter/ix_adapter.py",
            "Tools/ContinuationController/continuation_controller.py",
            "Tools/LayeredMemoryController/layered_memory_controller.py",
            "Tools/ExecutionOrchestrator/execution_orchestrator.py",
            "Tools/ExecutionPolicyValidator/validate_execution_policies.py",
            "docs/external-intelligence-control-plane.md",
            "docs/team-safe-portable-import.md",
            "docs/orchestrator-evidence-admission-boundary.md",
            "docs/runtime-control-state.md",
            "docs/execution-control-plane-acceptance.md",
            "docs/execution-control-plane-threat-model.md",
            "examples/execution-orchestrator-personal-prepare.json",
            "examples/execution-orchestrator-team-safe-portable-import.json",
        ]
        missing = [relative for relative in required if not (root / relative).is_file()]
        self.assertEqual(missing, [], f"Missing required control-plane artifacts: {missing}")

    def test_runtime_state_and_evidence_are_git_ignored(self):
        root = Path(__file__).resolve().parents[2]
        ignore = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/STATE/", ignore)
        self.assertIn("/Evidence/", ignore)
        self.assertIn("__pycache__/", ignore)


if __name__ == "__main__":
    unittest.main()
