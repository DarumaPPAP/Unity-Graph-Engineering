#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--status", default="completed")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--execution-class", default="fixture")
    parser.add_argument("--provider", default="fixture-provider")
    parser.add_argument("--model", default="fixture-model")
    parser.add_argument("--agent-id", default="fixture-agent")
    parser.add_argument("--request-log", type=Path, default=None)
    args = parser.parse_args()

    if args.sleep_seconds > 0:
        time.sleep(args.sleep_seconds)

    request = json.loads(args.request.read_text(encoding="utf-8"))
    if args.request_log is not None:
        args.request_log.parent.mkdir(parents=True, exist_ok=True)
        args.request_log.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
                "status": args.status,
                "execution_class": args.execution_class,
                "agent_id": args.agent_id,
                "provider": args.provider,
                "model": args.model,
                "model_revision": "fixture-revision",
                "infrastructure_attempts": 1,
                "tool_manifest_hash": "fixture-tools",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return args.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
