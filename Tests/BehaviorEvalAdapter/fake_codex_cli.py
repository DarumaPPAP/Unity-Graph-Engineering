#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _value(args: list[str], flag: str) -> str:
    index = args.index(flag)
    return args[index + 1]


def main() -> int:
    args = sys.argv[1:]
    if args == ["--version"]:
        print("codex-cli 0.test")
        return 0
    if not args or args[0] != "exec":
        print("expected exec", file=sys.stderr)
        return 2

    workspace = Path(_value(args, "--cd"))
    final_path = Path(_value(args, "--output-last-message"))
    model = _value(args, "--model")
    prompt = args[-1]

    if not (workspace / ".unityagent-control" / "AGENTS.md").is_file():
        print("missing UnityAgent control snapshot", file=sys.stderr)
        return 3
    if "Golden expectations" not in prompt or "Maximum Agent attempts: 1" not in prompt:
        print("missing production prompt contract", file=sys.stderr)
        return 4

    mutate = os.environ.get("FAKE_CODEX_MUTATE", "").strip()
    if mutate:
        target = workspace / mutate
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("public sealed class CameraDebugger { public int FixedValue => 1; }\n", encoding="utf-8")

    route = os.environ.get("FAKE_CODEX_ROUTE", "architecture-design")
    response = {
        "response_markdown": f"Fake Codex production response for {model}. Compile evidence is not claimed unless observed.",
        "route": route,
        "fingerprint": {
            "intent": "review",
            "artifact": "architecture",
            "scope": "local",
            "failure_mode": "none",
            "architecture_state": "undecided",
            "mutation_target": "none" if not mutate else "source",
            "evidence_state": "partial",
            "project_access": "not_required",
        },
        "loaded_policies": [
            {
                "id": "minimum_cohesive_solution_first",
                "source_path": ".unityagent-control/.ai/user-policy.yaml#minimum_cohesive_solution_first",
                "reason": "minimum cohesive solution",
            }
        ],
        "loaded_knowledge": [],
        "quality_gates": [
            {
                "id": "architecture_fit",
                "requirement": "required",
                "status": "passed",
                "evidence": "static architecture review",
            }
        ],
        "execution_evidence": [],
        "unresolved_bindings": [],
        "execution_status": "passed",
    }
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 20}}))
    return int(os.environ.get("FAKE_CODEX_EXIT_CODE", "0"))


if __name__ == "__main__":
    raise SystemExit(main())
