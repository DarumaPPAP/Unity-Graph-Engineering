#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    request = json.loads(args.request.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    generated = args.output / "generated"
    generated.mkdir()
    (generated / "CameraDebugger.cs").write_text(
        "public sealed class CameraDebugger { }\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": "3.1",
        "manifest": {"id": "behavior-fixture-manifest", "attempt": 1},
        "task": {
            "id": request.get("golden_task_id"),
            "route": "architecture-design",
            "fingerprint": {
                "intent": "fixture",
                "artifact": "csharp",
                "scope": "local",
                "failure_mode": "none",
                "architecture_state": "existing",
                "mutation_target": "none",
                "evidence_state": "static",
                "project_access": "generic_planning",
            },
        },
        "policy": {"loaded": []},
        "knowledge": {"loaded": []},
        "harness": {"quality_gates": []},
        "execution": {"evidence": [], "unresolved_bindings": [], "status": "passed"},
    }
    (args.output / "context-manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    (args.output / "response.md").write_text("Fixture behavior response.\n", encoding="utf-8")
    (args.output / "artifact-index.yaml").write_text(
        yaml.safe_dump(
            {
                "artifacts": [
                    {
                        "path": "generated/CameraDebugger.cs",
                        "language": "csharp",
                        "kind": "generated_source",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (args.output / "execution-metadata.yaml").write_text(
        yaml.safe_dump(
            {
                "status": "completed",
                "provider": "fixture-provider",
                "model": "fixture-model",
                "model_revision": "fixture-revision",
                "infrastructure_attempts": 1,
                "tool_manifest_hash": "fixture-tools",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
