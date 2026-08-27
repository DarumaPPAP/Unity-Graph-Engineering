#!/usr/bin/env python3
"""Launch Phase 1.1 production_smoke using the hardened local Codex CLI bridge."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "Tools" / "CodexProductionAgent" / "codex_production_agent_v2.py"
SMOKE_LAUNCHER = ROOT / "Tools" / "BehaviorEvalAdapter" / "run_production_smoke.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unityagent-root", type=Path, required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--case", "--only-case", dest="only_case", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=150.0)
    parser.add_argument("--model", default=None)
    parser.add_argument("--reasoning-effort", default="high", choices=("low", "medium", "high", "xhigh"))
    parser.add_argument("--keep-mcp", action="store_true")
    args = parser.parse_args()

    if args.timeout_seconds <= 30.0:
        print("Codex production smoke setup failed: timeout must be greater than 30 seconds", file=sys.stderr)
        return 30

    agent_command = [sys.executable, str(BRIDGE)]
    bridge_timeout = max(1.0, args.timeout_seconds - 30.0)
    agent_command.extend([
        "--timeout-seconds", str(bridge_timeout),
        "--reasoning-effort", args.reasoning_effort,
    ])
    if args.model:
        agent_command.extend(["--model", args.model])
    if args.keep_mcp:
        agent_command.append("--keep-mcp")

    command = [
        sys.executable,
        str(SMOKE_LAUNCHER),
        "--unityagent-root",
        str(args.unityagent_root.resolve()),
        "--agent-command-json",
        json.dumps(agent_command),
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]
    if args.run_id:
        command.extend(["--run-id", args.run_id])
    if args.only_case:
        command.extend(["--case", args.only_case])

    completed = subprocess.run(command, cwd=ROOT, check=False, shell=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
