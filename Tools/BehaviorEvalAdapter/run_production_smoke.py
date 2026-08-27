#!/usr/bin/env python3
"""Run UnityAgent Phase 1.1 Real Actual Behavior smoke against a real Production Agent."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "Tools" / "BehaviorEvalAdapter" / "behavior_eval_adapter_v2.py"
DEFAULT_TIMEOUT_SECONDS = 150.0


class ProductionSmokeError(ValueError):
    """Production smoke setup is invalid."""


def _unityagent_root(cli_root: Path | None) -> Path:
    raw = str(cli_root) if cli_root is not None else os.environ.get("UNITYAGENT_ROOT", "")
    if not raw.strip():
        raise ProductionSmokeError("UnityAgent checkout root is required via --unityagent-root or UNITYAGENT_ROOT")
    root = Path(raw).expanduser().resolve()
    runner = root / "Tools" / "BehaviorEval" / "run_behavior_eval.py"
    suites = root / "Tests" / "BehaviorEval" / "suites.yaml"
    contracts = root / "Tests" / "BehaviorEval" / "production-smoke-contracts.yaml"
    if not root.is_dir() or not runner.is_file() or not suites.is_file() or not contracts.is_file():
        raise ProductionSmokeError(f"Configured UnityAgent root is incomplete for Phase 1.1: {root}")
    return root


def _load_agent_command(cli_value: str | None) -> tuple[str, list[str]]:
    raw = cli_value or os.environ.get("UNITYAGENT_PRODUCTION_COMMAND_JSON", "")
    if not raw:
        raise ProductionSmokeError(
            "Real Production Agent command is required via --agent-command-json or UNITYAGENT_PRODUCTION_COMMAND_JSON"
        )
    try:
        command = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProductionSmokeError("Production Agent command must be a JSON array") from exc
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        raise ProductionSmokeError("Production Agent command must be a non-empty JSON string array")
    lowered = [item.replace("\\", "/").lower() for item in command]
    if any(token.endswith("fake_production_agent.py") for token in lowered):
        raise ProductionSmokeError("Phase 1.1 production smoke refuses the fake Production Agent fixture")
    return raw, command


def _run_id(value: str | None) -> str:
    if value:
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise ProductionSmokeError("run-id must be a single safe path segment")
        return value
    return datetime.now(timezone.utc).strftime("production-smoke-v2-%Y%m%d-%H%M%S")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unityagent-root", type=Path, default=None)
    parser.add_argument("--agent-command-json", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--case", "--only-case", dest="only_case", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    try:
        if args.timeout_seconds <= 0:
            raise ProductionSmokeError("--timeout-seconds must be greater than zero")
        unityagent_root = _unityagent_root(args.unityagent_root)
        raw_command, _ = _load_agent_command(args.agent_command_json)
        run_id = _run_id(args.run_id)
    except (OSError, ProductionSmokeError) as exc:
        print(f"Production Behavior Smoke setup failed: {exc}", file=sys.stderr)
        return 30

    runner = unityagent_root / "Tools" / "BehaviorEval" / "run_behavior_eval.py"
    adapter_command = [
        sys.executable,
        str(ADAPTER),
        "--unityagent-root",
        str(unityagent_root),
        "--timeout-seconds",
        str(args.timeout_seconds),
        "--require-production-identity",
    ]
    command = [
        sys.executable,
        str(runner),
        "--suite",
        "production_smoke",
        "--run-id",
        run_id,
    ]
    if args.only_case:
        command.extend(["--case", args.only_case])
    command.extend(["--executor-command", *adapter_command])

    env = os.environ.copy()
    env["UNITYAGENT_ROOT"] = str(unityagent_root)
    env["UNITYAGENT_PRODUCTION_COMMAND_JSON"] = raw_command
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        command,
        cwd=unityagent_root,
        check=False,
        shell=False,
        env=env,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
