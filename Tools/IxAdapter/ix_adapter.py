#!/usr/bin/env python3
"""Safe optional adapter for the Ix code-intelligence CLI.

This adapter intentionally exposes only bounded read/navigation operations.
It never installs Ix and never exposes destructive Ix commands such as reset.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"
PROVIDER = "ix"
DEFAULT_QUERY_TIMEOUT_SECONDS = 30
DEFAULT_MAP_TIMEOUT_SECONDS = 120
DEFAULT_TRACE_DEPTH = 3
DEFAULT_TRACE_CAP = 100
DEFAULT_MIN_CONFIDENCE = 0.5

SAFE_OPERATIONS = {
    "probe",
    "status",
    "map",
    "explain",
    "impact",
    "trace",
    "callers",
    "callees",
}

TRACE_KINDS = {"calls", "imports", "depends", "contains"}
TRACE_DIRECTIONS = {"both", "upstream", "downstream"}


def _safe_symbol(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("target symbol must not be empty")
    if value.startswith("-"):
        raise ValueError("target symbol must not start with '-'")
    if any(ch in value for ch in ("\x00", "\r", "\n")):
        raise ValueError("target symbol contains forbidden control characters")
    return value


def _repo_root(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"repo root does not exist or is not a directory: {path}")
    return path


def _parse_json_output(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        return {}
    return json.loads(text)


def _confidence_values(value: Any) -> Iterable[float]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() == "confidence":
                if isinstance(child, (int, float)) and not isinstance(child, bool):
                    numeric = float(child)
                    if 0.0 <= numeric <= 1.0:
                        yield numeric
                elif isinstance(child, str):
                    lowered = child.strip().lower()
                    if lowered in {"low", "uncertain"}:
                        yield 0.0
                    elif lowered in {"medium", "moderate"}:
                        yield 0.5
                    elif lowered in {"high", "verified"}:
                        yield 1.0
            yield from _confidence_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _confidence_values(child)


def _envelope(
    *,
    operation: str,
    status: str,
    available: bool,
    exit_code: int | None = None,
    data: Any = None,
    diagnostics: list[dict[str, Any]] | None = None,
    fallback: str | None = None,
    confidence_min: float | None = None,
    low_confidence: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": PROVIDER,
        "operation": operation,
        "status": status,
        "available": available,
        "exit_code": exit_code,
        "data": data,
        "diagnostics": diagnostics or [],
        "fallback": fallback,
        "confidence_min": confidence_min,
        "low_confidence": low_confidence,
    }


def _run_ix(
    repo_root: Path,
    operation: str,
    args: list[str],
    *,
    timeout_seconds: int,
    expect_json: bool,
    min_confidence: float,
) -> dict[str, Any]:
    executable = shutil.which("ix")
    if executable is None:
        return _envelope(
            operation=operation,
            status="unavailable",
            available=False,
            diagnostics=[{"code": "ix_cli_not_found", "message": "Ix CLI was not found on PATH."}],
            fallback="targeted_source_read",
        )

    command = [executable, *args]

    try:
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return _envelope(
            operation=operation,
            status="error",
            available=True,
            diagnostics=[
                {
                    "code": "ix_timeout",
                    "message": f"Ix command exceeded {timeout_seconds} seconds.",
                }
            ],
            fallback="targeted_source_read",
        )
    except OSError as exc:
        return _envelope(
            operation=operation,
            status="unavailable",
            available=False,
            diagnostics=[{"code": "ix_launch_failed", "message": str(exc)}],
            fallback="targeted_source_read",
        )

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        preview = stderr[:1000]
        status = "unavailable" if operation in {"probe", "status"} else "error"
        code = "ix_backend_unavailable" if operation in {"probe", "status"} else "ix_command_failed"
        return _envelope(
            operation=operation,
            status=status,
            available=operation not in {"probe", "status"},
            exit_code=completed.returncode,
            diagnostics=[{"code": code, "message": preview or "Ix command failed."}],
            fallback="targeted_source_read",
        )

    if not expect_json:
        return _envelope(
            operation=operation,
            status="ok",
            available=True,
            exit_code=completed.returncode,
            data={"completed": True},
        )

    try:
        data = _parse_json_output(completed.stdout or "")
    except json.JSONDecodeError as exc:
        preview = (completed.stdout or "").strip()[:1000]
        return _envelope(
            operation=operation,
            status="error",
            available=True,
            exit_code=completed.returncode,
            diagnostics=[
                {
                    "code": "ix_non_json_output",
                    "message": f"Ix returned non-JSON output: {exc}",
                    "preview": preview,
                }
            ],
            fallback="targeted_source_read",
        )

    confidences = list(_confidence_values(data))
    confidence_min = min(confidences) if confidences else None
    low_confidence = confidence_min is not None and confidence_min < min_confidence
    diagnostics: list[dict[str, Any]] = []
    if low_confidence:
        diagnostics.append(
            {
                "code": "ix_low_confidence",
                "message": (
                    f"Ix returned confidence {confidence_min:.3f}, below "
                    f"the adapter threshold {min_confidence:.3f}."
                ),
            }
        )

    return _envelope(
        operation=operation,
        status="ok",
        available=True,
        exit_code=completed.returncode,
        data=data,
        diagnostics=diagnostics,
        confidence_min=confidence_min,
        low_confidence=low_confidence,
    )


def build_operation_args(args: argparse.Namespace) -> tuple[list[str], bool]:
    operation = args.operation
    if operation not in SAFE_OPERATIONS:
        raise ValueError(f"unsupported operation: {operation}")

    if operation in {"probe", "status"}:
        return ["status", "--format", "json"], True

    if operation == "map":
        return ["map", "--silent"], False

    target = _safe_symbol(args.target)

    if operation == "trace":
        command = [
            "trace",
            target,
            "--depth",
            str(args.depth),
            "--cap",
            str(args.cap),
            "--format",
            "json",
        ]
        if args.direction == "upstream":
            command.append("--upstream")
        elif args.direction == "downstream":
            command.append("--downstream")
        if args.kind:
            command.extend(["--kind", args.kind])
        if args.include_tests:
            command.append("--include-tests")
        return command, True

    return [operation, target, "--format", "json"], True


def execute(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = _repo_root(args.repo_root)
    command_args, expect_json = build_operation_args(args)
    timeout = args.timeout
    if timeout is None:
        timeout = DEFAULT_MAP_TIMEOUT_SECONDS if args.operation == "map" else DEFAULT_QUERY_TIMEOUT_SECONDS

    return _run_ix(
        repo_root,
        args.operation,
        command_args,
        timeout_seconds=timeout,
        expect_json=expect_json,
        min_confidence=args.min_confidence,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run bounded Ix code-intelligence operations and emit a normalized JSON envelope. "
            "This tool never installs Ix and never exposes destructive Ix commands."
        )
    )
    parser.add_argument(
        "operation",
        choices=sorted(SAFE_OPERATIONS),
        help="Allowed Ix operation.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Symbol/entity for explain, impact, trace, callers, or callees.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Mapped repository root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Command timeout in seconds. Defaults to 30s, or 120s for map.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_MIN_CONFIDENCE,
        help="Mark results below this 0..1 confidence as low-confidence.",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=DEFAULT_TRACE_DEPTH,
        help="Trace traversal depth. Trace only.",
    )
    parser.add_argument(
        "--cap",
        type=int,
        default=DEFAULT_TRACE_CAP,
        help="Trace node cap per direction. Trace only.",
    )
    parser.add_argument(
        "--direction",
        choices=sorted(TRACE_DIRECTIONS),
        default="both",
        help="Trace direction. Trace only.",
    )
    parser.add_argument(
        "--kind",
        choices=sorted(TRACE_KINDS),
        default=None,
        help="Trace relationship kind. Trace only.",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Allow Ix trace to include test/fixture entities.",
    )
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    requires_target = args.operation in {"explain", "impact", "trace", "callers", "callees"}
    if requires_target and not args.target:
        raise ValueError(f"{args.operation} requires a target symbol")
    if not requires_target and args.target:
        raise ValueError(f"{args.operation} does not accept a target symbol")
    if args.timeout is not None and args.timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    if not 0.0 <= args.min_confidence <= 1.0:
        raise ValueError("min-confidence must be between 0 and 1")
    if args.depth <= 0:
        raise ValueError("depth must be greater than zero")
    if args.cap <= 0:
        raise ValueError("cap must be greater than zero")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        _validate_args(args)
        result = execute(args)
    except ValueError as exc:
        result = _envelope(
            operation=getattr(args, "operation", "unknown"),
            status="invalid_request",
            available=shutil.which("ix") is not None,
            diagnostics=[{"code": "invalid_request", "message": str(exc)}],
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] == "ok":
        return 0
    if result["status"] == "unavailable":
        return 2
    if result["status"] == "invalid_request":
        return 4
    return 3


if __name__ == "__main__":
    sys.exit(main())
